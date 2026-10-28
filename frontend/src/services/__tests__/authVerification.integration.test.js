/**
 * Contract test: the real frontend authService against the REAL backend, with
 * the backend using a mock email provider (nothing is emailed).
 *
 * Skipped unless FITFLOW_E2E_URL is set. To run it:
 *
 *   1. cd backend && ../venv/Scripts/python tests/e2e_server.py --port 8765
 *   2. cd frontend
 *      FITFLOW_E2E_URL=http://127.0.0.1:8765 REACT_APP_API_URL=http://127.0.0.1:8765/api \
 *        CI=true npx react-scripts test --watchAll=false --runInBand authVerification.integration
 *
 * @jest-environment node
 */

// Minimal browser globals the service layer touches (this suite runs in Node,
// which avoids browser CORS rules; CORS is checked separately).
global.window = { location: { pathname: '/', href: '' } };
const mockStore = {};
global.localStorage = {
  getItem: (key) => (key in mockStore ? mockStore[key] : null),
  setItem: (key, value) => { mockStore[key] = String(value); },
  removeItem: (key) => { delete mockStore[key]; },
};

// axios 1.x ships ESM at its package "main", which Jest 27 cannot load; use its CommonJS build.
jest.mock('axios', () => require('axios/dist/node/axios.cjs'));

const axios = require('axios');
const authService = require('../authService').default;

const E2E_URL = process.env.FITFLOW_E2E_URL;
const describeE2E = E2E_URL ? describe : describe.skip;

const emailedCodes = async (email) =>
  (await axios.get(`${E2E_URL}/__test__/codes`, { params: { email } })).data.codes;

const rejection = async (promise) => {
  try {
    await promise;
  } catch (err) {
    return err.response;
  }
  throw new Error('expected the request to be rejected');
};

describeE2E('authService ↔ real backend (mock email provider)', () => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = 'correct-horse-battery';

  test('signup creates an UNVERIFIED account and emails one 6-digit code', async () => {
    const created = await authService.signup(email, password);
    expect(created.is_verified).toBe(false);
    expect(created.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(created).not.toHaveProperty('hashed_password');

    const codes = await emailedCodes(email);
    expect(codes).toHaveLength(1);
    expect(codes[0]).toMatch(/^\d{6}$/);
  });

  test('login is refused with 403 until the code is confirmed', async () => {
    const response = await rejection(authService.login(email, password));
    expect(response.status).toBe(403);
    expect(response.data.detail).toMatch(/not verified/i);
    expect(authService.isLoggedIn()).toBe(false);
  });

  test('an immediate resend hits the cooldown (429 + Retry-After)', async () => {
    const response = await rejection(authService.resendOtp(email));
    expect(response.status).toBe(429);
    expect(parseInt(response.headers['retry-after'], 10)).toBeGreaterThan(0);
    expect(await emailedCodes(email)).toHaveLength(1);
  });

  test('a wrong code is rejected without leaking the real one', async () => {
    const [real] = await emailedCodes(email);
    const wrong = real === '000000' ? '111111' : '000000';
    const response = await rejection(authService.verifyOtp(email, wrong));
    expect(response.status).toBe(400);
    expect(JSON.stringify(response.data)).not.toContain(real);
  });

  test('the emailed code verifies the account, then login and /users/me work', async () => {
    const [code] = await emailedCodes(email);
    const verified = await authService.verifyOtp(email, code);
    expect(verified.message).toMatch(/verified/i);

    const login = await authService.login(email, password);
    expect(login.access_token).toBeTruthy();
    expect(authService.isLoggedIn()).toBe(true);

    const me = await authService.getCurrentUser();
    expect(me.email).toBe(email);
    expect(me.is_verified).toBe(true);
  });

  test('the code is single-use and a duplicate signup is rejected', async () => {
    const [code] = await emailedCodes(email);
    expect((await rejection(authService.verifyOtp(email, code))).status).toBe(400);
    expect((await rejection(authService.signup(email, 'another-password'))).status).toBe(400);
  });

  test('resend for an already-verified account is a silent no-op', async () => {
    const result = await authService.resendOtp(email);
    expect(result.message).toMatch(/if this email/i);
    expect(await emailedCodes(email)).toHaveLength(1);
  });
});
