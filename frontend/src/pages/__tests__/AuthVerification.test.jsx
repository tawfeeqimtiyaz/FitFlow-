import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import { AuthProvider } from '../../context/AuthContext';
import Signup from '../Signup';
import Login from '../Login';

jest.setTimeout(20000);

// react-scripts 5 bundles Jest 27, which cannot resolve react-router v7's
// package "exports" (and react-router-dom's "main" points at a missing file).
// Point both at the real CommonJS builds. Webpack (the app itself) is unaffected.
// It also needs TextEncoder, which Jest 27's jsdom lacks, so that is supplied
// from Node's util before the router loads.
jest.mock('react-router/dom', () => require('react-router/dist/development/dom-export.js'), { virtual: true });
jest.mock('react-router-dom', () => {
  const { TextEncoder, TextDecoder } = require('util');
  global.TextEncoder = global.TextEncoder || TextEncoder;
  global.TextDecoder = global.TextDecoder || TextDecoder;
  return require('react-router-dom/dist/index.js');
}, { virtual: true });

// ── In-memory stand-in for the FitFlow API ───────────────────────────────────
// Sits *behind* the real authService / AuthContext / pages and follows the same
// rules as the real backend (cooldown, attempt limit, 403 before verification).
// `mockMailbox` plays the role of the mock email provider: no real email is sent.
const mockMailbox = [];

const mockBackend = {
  state: {},

  reset() {
    mockMailbox.length = 0;
    this.state = {
      users: {},
      sendCount: 0,
      verificationRequired: true,
      resendLocked: false,
      hideRetryAfter: false,
      offline: false,
    };
    localStorage.clear();
  },

  fail(status, detail, headers = {}) {
    return Promise.reject({ response: { status, data: { detail }, headers } });
  },

  mail(email) {
    this.state.sendCount += 1;
    const code = String(this.state.sendCount).repeat(6).slice(0, 6);   // 111111, 222222, ...
    this.state.users[email].code = code;
    this.state.users[email].attempts = 0;
    mockMailbox.push({ to: email, code });
    return code;
  },

  // Used by tests to create an account that signed up earlier but never verified
  seedUnverified(email, password) {
    this.state.users[email] = { password, verified: false };
    return this.mail(email);
  },

  post(url, body) {
    const { users } = this.state;
    if (this.state.offline) return Promise.reject(new Error('Network Error'));

    if (url === '/auth/signup') {
      if (users[body.email]) return this.fail(400, 'Email already registered');
      users[body.email] = { password: body.password, verified: !this.state.verificationRequired };
      if (this.state.verificationRequired) this.mail(body.email);
      return Promise.resolve({
        data: { id: 'user-1', email: body.email, is_active: true, is_verified: !this.state.verificationRequired },
      });
    }

    if (url === '/auth/verify-otp') {
      const user = users[body.email];
      if (!user) return this.fail(400, 'Invalid or expired verification code');
      if (user.verified) return this.fail(400, 'Email is already verified');
      if (user.attempts >= 5) return this.fail(429, 'Too many incorrect attempts. Please request a new code.');
      if (body.otp !== user.code) {
        user.attempts += 1;
        return user.attempts >= 5
          ? this.fail(429, 'Too many incorrect attempts. Please request a new code.')
          : this.fail(400, 'Invalid or expired verification code');
      }
      user.verified = true;
      return Promise.resolve({ data: { message: 'Email verified. You can now log in.' } });
    }

    if (url === '/auth/resend-otp') {
      if (this.state.resendLocked) {
        return this.fail(
          429,
          'Please wait 30 seconds before requesting another code.',
          this.state.hideRetryAfter ? {} : { 'retry-after': '30' }
        );
      }
      const user = users[body.email];
      if (user && !user.verified) this.mail(body.email);
      return Promise.resolve({
        data: { message: 'If this email has an unverified account, a new verification code has been sent.' },
      });
    }

    if (url === '/auth/login') {
      const email = body.get('username');
      const user = users[email];
      if (!user || user.password !== body.get('password')) return this.fail(401, 'Incorrect email or password');
      if (this.state.verificationRequired && !user.verified) {
        return this.fail(403, 'Email not verified. Enter the verification code we emailed you, or request a new one.');
      }
      return Promise.resolve({ data: { access_token: `token-for-${email}`, token_type: 'bearer' } });
    }

    return Promise.reject(new Error(`unexpected POST ${url}`));
  },

  get(url) {
    if (url === '/users/me') {
      const token = localStorage.getItem('token') || '';
      return Promise.resolve({ data: { id: 'user-1', email: token.replace('token-for-', ''), is_active: true } });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  },
};

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {
    post: (...args) => mockBackend.post(...args),
    get: (...args) => mockBackend.get(...args),
  },
}));

// ── Helpers ──────────────────────────────────────────────────────────────────
const renderAuth = (path = '/signup') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/signup" element={<Signup />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<div>Dashboard page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );

const EMAIL = 'runner@example.com';
const PASSWORD = 'correct-horse';

const fillAndSubmitSignup = async (email = EMAIL, password = PASSWORD) => {
  userEvent.type(await screen.findByLabelText(/^email$/i), email);
  userEvent.type(screen.getByLabelText(/^password$/i), password);
  userEvent.type(screen.getByLabelText(/confirm password/i), password);
  userEvent.click(screen.getByRole('button', { name: /^sign up$/i }));
};

const verifyHeading = () => screen.findByRole('heading', { name: /verify your email/i });
const codeInput = () => screen.getByLabelText(/verification code/i);
const verifyButton = () => screen.getByRole('button', { name: /^verify email$/i });

beforeEach(() => mockBackend.reset());

afterEach(() => {
  jest.useRealTimers();
});

// ── Tests ────────────────────────────────────────────────────────────────────
describe('signup → OTP verification → login', () => {
  test('complete flow: signup, enter the emailed code, land on login, sign in', async () => {
    renderAuth();
    await fillAndSubmitSignup();

    // Step 2 appears and exactly one code was "emailed"
    await verifyHeading();
    expect(screen.getByText(EMAIL)).toBeInTheDocument();
    expect(mockMailbox).toHaveLength(1);
    expect(mockMailbox[0].to).toBe(EMAIL);

    // Cannot submit until all six digits are in; resend starts on cooldown
    expect(verifyButton()).toBeDisabled();
    expect(screen.getByRole('button', { name: /resend code in 60s/i })).toBeDisabled();

    userEvent.type(codeInput(), mockMailbox[0].code);
    expect(verifyButton()).toBeEnabled();
    userEvent.click(verifyButton());

    expect(await screen.findByText(/email verified! redirecting to login/i)).toBeInTheDocument();

    // Redirected to login, email prefilled, success note shown
    await screen.findByRole('heading', { name: /welcome back/i }, { timeout: 4000 });
    expect(screen.getByLabelText(/^email$/i)).toHaveValue(EMAIL);
    expect(screen.getByText(/you can now log in/i)).toBeInTheDocument();

    userEvent.type(screen.getByLabelText(/^password$/i), PASSWORD);
    userEvent.click(screen.getByRole('button', { name: /^login$/i }));
    expect(await screen.findByText('Dashboard page')).toBeInTheDocument();
    expect(localStorage.getItem('token')).toBe(`token-for-${EMAIL}`);
  });

  test('the code field accepts digits only and at most six', async () => {
    renderAuth();
    await fillAndSubmitSignup();
    await verifyHeading();

    userEvent.type(codeInput(), '12ab 34-567890');
    expect(codeInput()).toHaveValue('123456');

    userEvent.clear(codeInput());
    userEvent.type(codeInput(), '12345');
    expect(verifyButton()).toBeDisabled();
  });

  test('a wrong code shows an error, clears the field, and the right code still works', async () => {
    renderAuth();
    await fillAndSubmitSignup();
    await verifyHeading();

    userEvent.type(codeInput(), '000000');
    userEvent.click(verifyButton());
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid or expired verification code');
    expect(codeInput()).toHaveValue('');

    userEvent.type(codeInput(), mockMailbox[0].code);
    userEvent.click(verifyButton());
    expect(await screen.findByText(/email verified/i)).toBeInTheDocument();
  });

  test('too many wrong codes shows the lock-out message from the server', async () => {
    renderAuth();
    await fillAndSubmitSignup();
    await verifyHeading();

    for (let attempt = 1; attempt <= 5; attempt += 1) {
      userEvent.type(codeInput(), '000000');
      userEvent.click(verifyButton());
      await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
      await waitFor(() => expect(codeInput()).toHaveValue(''));
    }
    expect(screen.getByRole('alert')).toHaveTextContent(/too many incorrect attempts/i);
  });

  test('resend is locked for 60s, then sends a fresh code and locks again', async () => {
    jest.useFakeTimers();
    renderAuth();
    await fillAndSubmitSignup();
    await verifyHeading();

    const locked = () => screen.getByRole('button', { name: /resend code in \d+s/i });
    expect(locked()).toBeDisabled();

    // Advance one second at a time so each countdown tick can re-render
    for (let second = 0; second < 59; second += 1) act(() => { jest.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: /resend code in 1s/i })).toBeDisabled();

    act(() => { jest.advanceTimersByTime(1000); });
    const resend = screen.getByRole('button', { name: /^resend code$/i });
    expect(resend).toBeEnabled();

    userEvent.type(codeInput(), '12'); // partly typed code is discarded on resend
    userEvent.click(resend);

    expect(await screen.findByText(/new verification code has been sent/i)).toBeInTheDocument();
    expect(mockMailbox).toHaveLength(2);
    expect(codeInput()).toHaveValue('');
    expect(locked()).toBeDisabled();

    // The new code is the one that works
    userEvent.type(codeInput(), mockMailbox[1].code);
    userEvent.click(verifyButton());
    expect(await screen.findByText(/email verified/i)).toBeInTheDocument();
  });

  test('duplicate signup shows the server error and stays on the form', async () => {
    mockBackend.state.users[EMAIL] = { password: 'someone-else', verified: true };
    renderAuth();
    await fillAndSubmitSignup();

    expect(await screen.findByText('Email already registered')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /verify your email/i })).not.toBeInTheDocument();
    expect(mockMailbox).toHaveLength(0);
  });

  test('client-side checks still run before any request is made', async () => {
    renderAuth();
    userEvent.type(await screen.findByLabelText(/^email$/i), EMAIL);
    userEvent.type(screen.getByLabelText(/^password$/i), PASSWORD);
    userEvent.type(screen.getByLabelText(/confirm password/i), 'different-password');
    userEvent.click(screen.getByRole('button', { name: /^sign up$/i }));

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
    expect(Object.keys(mockBackend.state.users)).toHaveLength(0);
  });

  test('an unreachable server gives a clear message instead of a crash', async () => {
    mockBackend.state.offline = true;
    renderAuth();
    await fillAndSubmitSignup();
    expect(await screen.findByText(/cannot reach the server/i)).toBeInTheDocument();
  });

  test('when the server has verification switched off, signup behaves as before', async () => {
    mockBackend.state.verificationRequired = false;
    renderAuth();
    await fillAndSubmitSignup();

    expect(await screen.findByText(/account created! redirecting to login/i)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /verify your email/i })).not.toBeInTheDocument();
    expect(mockMailbox).toHaveLength(0);
    await screen.findByRole('heading', { name: /welcome back/i }, { timeout: 4000 });
  });

  test('"Already have a verification code?" lets a returning user verify with their email', async () => {
    const code = mockBackend.seedUnverified(EMAIL, PASSWORD);
    renderAuth();

    userEvent.click(await screen.findByRole('button', { name: /already have a verification code/i }));
    await verifyHeading();

    userEvent.type(screen.getByLabelText(/^email$/i), EMAIL);
    userEvent.type(codeInput(), code);
    userEvent.click(verifyButton());
    expect(await screen.findByText(/email verified/i)).toBeInTheDocument();
  });
});

describe('login before verification', () => {
  test('a 403 explains why and links to the verification step with the email filled in', async () => {
    const code = mockBackend.seedUnverified(EMAIL, PASSWORD);
    renderAuth('/login');

    userEvent.type(await screen.findByLabelText(/^email$/i), EMAIL);
    userEvent.type(screen.getByLabelText(/^password$/i), PASSWORD);
    userEvent.click(screen.getByRole('button', { name: /^login$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/email not verified/i);
    expect(localStorage.getItem('token')).toBeNull();

    userEvent.click(screen.getByRole('link', { name: /verify your email/i }));
    await verifyHeading();
    expect(screen.getByText(EMAIL)).toBeInTheDocument();
    expect(screen.getByText(/enter the code we emailed you/i)).toBeInTheDocument();
    // Arrived from login: nothing was just sent, so resend is available at once
    expect(screen.getByRole('button', { name: /^resend code$/i })).toBeEnabled();

    userEvent.type(codeInput(), code);
    userEvent.click(verifyButton());
    expect(await screen.findByText(/email verified/i)).toBeInTheDocument();
  });

  test('server-side cooldown (429 + Retry-After) locks the resend button for that long', async () => {
    mockBackend.seedUnverified(EMAIL, PASSWORD);
    mockBackend.state.resendLocked = true;
    renderAuth('/login');

    userEvent.type(await screen.findByLabelText(/^email$/i), EMAIL);
    userEvent.type(screen.getByLabelText(/^password$/i), PASSWORD);
    userEvent.click(screen.getByRole('button', { name: /^login$/i }));
    userEvent.click(await screen.findByRole('link', { name: /verify your email/i }));
    await verifyHeading();

    userEvent.click(screen.getByRole('button', { name: /^resend code$/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/please wait 30 seconds/i);
    expect(screen.getByRole('button', { name: /resend code in 30s/i })).toBeDisabled();
    expect(mockMailbox).toHaveLength(1);   // nothing extra was sent
  });

  test('if the Retry-After header is hidden from the browser, the default 60s cooldown applies', async () => {
    mockBackend.seedUnverified(EMAIL, PASSWORD);
    mockBackend.state.resendLocked = true;
    mockBackend.state.hideRetryAfter = true;
    renderAuth('/login');

    userEvent.type(await screen.findByLabelText(/^email$/i), EMAIL);
    userEvent.type(screen.getByLabelText(/^password$/i), PASSWORD);
    userEvent.click(screen.getByRole('button', { name: /^login$/i }));
    userEvent.click(await screen.findByRole('link', { name: /verify your email/i }));
    await verifyHeading();

    userEvent.click(screen.getByRole('button', { name: /^resend code$/i }));
    expect(await screen.findByRole('button', { name: /resend code in 60s/i })).toBeDisabled();
  });

  test('wrong password is still a plain error with no verification link', async () => {
    mockBackend.seedUnverified(EMAIL, PASSWORD);
    renderAuth('/login');

    userEvent.type(await screen.findByLabelText(/^email$/i), EMAIL);
    userEvent.type(screen.getByLabelText(/^password$/i), 'not-it');
    userEvent.click(screen.getByRole('button', { name: /^login$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password');
    expect(screen.queryByRole('link', { name: /verify your email/i })).not.toBeInTheDocument();
  });

  test('a verified user logs in normally', async () => {
    mockBackend.state.users[EMAIL] = { password: PASSWORD, verified: true };
    renderAuth('/login');

    userEvent.type(await screen.findByLabelText(/^email$/i), EMAIL);
    userEvent.type(screen.getByLabelText(/^password$/i), PASSWORD);
    userEvent.click(screen.getByRole('button', { name: /^login$/i }));
    expect(await screen.findByText('Dashboard page')).toBeInTheDocument();
  });
});
