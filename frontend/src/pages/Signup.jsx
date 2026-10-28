import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import authService from '../services/authService';
import './Auth.css';

const OTP_LENGTH = 6;
// Mirrors the backend default (OTP_RESEND_COOLDOWN_SECONDS). If the server
// says otherwise (429 + Retry-After) the countdown follows the server.
const RESEND_COOLDOWN_SECONDS = 60;

// Turn an Axios error into something safe and readable for the user
const getErrorMessage = (err, fallback) => {
  if (!err.response) {
    return 'Cannot reach the server. Please check your connection and try again.';
  }
  const detail = err.response.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
};

const Signup = () => {
  // Arriving from the login page's "verify your email" link opens step 2 directly
  const location = useLocation();
  const verifyEmailFromLogin = location.state?.verifyEmail || '';

  const [step, setStep]                     = useState(verifyEmailFromLogin ? 'verify' : 'form');
  const [email, setEmail]                   = useState(verifyEmailFromLogin);
  const [password, setPassword]             = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [code, setCode]                     = useState('');
  const [askEmail, setAskEmail]             = useState(false);   // step 2 without a known email
  const [cooldown, setCooldown]             = useState(0);       // seconds until "resend" unlocks
  const [resending, setResending]           = useState(false);
  const [error, setError]                   = useState('');
  const [success, setSuccess]               = useState('');  // ✅ ADDED
  const [info, setInfo]                     = useState(
    verifyEmailFromLogin ? 'Enter the code we emailed you, or request a new one.' : ''
  );
  const [loading, setLoading]               = useState(false);

  const { signup, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const redirectTimer = useRef(null);

  // ✅ ADDED: Redirect if already logged in
  useEffect(() => {
    if (!authLoading && user) {
      navigate('/dashboard', { replace: true });
    }
  }, [user, authLoading, navigate]);

  // Resend countdown: one tick per second until it reaches zero
  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = setTimeout(() => setCooldown((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  // Never fire the post-verification redirect after the page is gone
  useEffect(() => () => clearTimeout(redirectTimer.current), []);

  const clearMessages = () => {
    setError('');
    setSuccess('');
    setInfo('');
  };

  // ── Step 1: create the account ────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    clearMessages();

    // ── Client-side validation ──────────────────────────────
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    // ✅ ADDED: Basic email format check
    if (!email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);

    try {
      const created = await signup(email, password);

      if (created && created.is_verified === false) {
        // The server emailed a one-time code: ask for it before login is possible
        setStep('verify');
        setAskEmail(false);
        setCode('');
        setCooldown(RESEND_COOLDOWN_SECONDS);
        setInfo(`We sent a ${OTP_LENGTH}-digit code to ${email}.`);
      } else {
        // Verification is switched off on the server: original behaviour
        setSuccess('Account created! Redirecting to login...');

        redirectTimer.current = setTimeout(() => {
          navigate('/login', { replace: true });
        }, 1500);                              // ✅ 1.5s so user sees message
      }

    } catch (err) {
      setError(getErrorMessage(err, 'Signup failed. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2: confirm the emailed code ──────────────────────────────────────
  const handleCodeChange = (e) => {
    // Digits only, at most OTP_LENGTH (also cleans up pasted codes like "123 456")
    setCode(e.target.value.replace(/\D/g, '').slice(0, OTP_LENGTH));
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    clearMessages();

    if (!email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    if (code.length !== OTP_LENGTH) {
      setError(`Enter the ${OTP_LENGTH}-digit code from your email`);
      return;
    }

    setLoading(true);

    try {
      await authService.verifyOtp(email, code);

      setSuccess('Email verified! Redirecting to login...');
      redirectTimer.current = setTimeout(() => {
        navigate('/login', { replace: true, state: { email, verified: true } });
      }, 1500);

    } catch (err) {
      setError(getErrorMessage(err, 'Verification failed. Please try again.'));
      if (err.response) setCode('');       // keep what was typed if the server was unreachable
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0 || resending) return;

    if (!email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    clearMessages();
    setResending(true);

    try {
      const result = await authService.resendOtp(email);
      setCode('');
      setCooldown(RESEND_COOLDOWN_SECONDS);
      setInfo(result?.message || 'A new code has been sent.');

    } catch (err) {
      setError(getErrorMessage(err, 'Could not send a new code. Please try again.'));

      // The server tells us how long to wait; keep the button locked until then.
      // (If a proxy hides the header, fall back to the default cooldown.)
      if (err.response?.status === 429) {
        const retryAfter = parseInt(err.response.headers?.['retry-after'], 10);
        setCooldown(retryAfter > 0 ? retryAfter : RESEND_COOLDOWN_SECONDS);
      }
    } finally {
      setResending(false);
    }
  };

  const backToForm = () => {
    clearMessages();
    setCode('');
    setCooldown(0);
    setStep('form');
  };

  const openVerifyStep = () => {
    clearMessages();
    setAskEmail(!email.includes('@'));
    setStep('verify');
  };

  // ✅ Don't flash signup form while checking auth
  if (authLoading) return null;

  // ── Render: step 2 ────────────────────────────────────────────────────────
  if (step === 'verify') {
    const verified = !!success;

    return (
      <div className="auth-page">
        <div className="auth-card">

          <h1 className="auth-title">Verify Your Email </h1>
          <p className="auth-subtitle">
            {askEmail
              ? `Enter your email and the ${OTP_LENGTH}-digit code we sent you`
              : <>Enter the {OTP_LENGTH}-digit code we sent to <strong>{email}</strong></>}
          </p>

          {error && <div className="auth-error" role="alert">{error}</div>}
          {success && <div className="auth-success" role="status">{success}</div>}
          {info && !error && !success && <div className="auth-info" role="status">{info}</div>}

          <form onSubmit={handleVerify} className="auth-form" noValidate>

            {askEmail && (
              <div className="form-group">
                <label className="form-label" htmlFor="verify-email">Email</label>
                <input
                  id="verify-email"
                  type="email"
                  className="form-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  autoComplete="email"
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="otp">Verification Code</label>
              <input
                id="otp"
                type="text"
                className="form-input otp-input"
                value={code}
                onChange={handleCodeChange}
                placeholder="------"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={OTP_LENGTH}
                autoComplete="one-time-code"
                autoFocus
                disabled={verified}
                required
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={loading || verified || code.length !== OTP_LENGTH}
            >
              {loading ? (
                <>
                  <span className="btn-spinner"></span>
                  Verifying...
                </>
              ) : (
                'Verify Email'
              )}
            </button>

          </form>

          <div className="auth-actions">
            <button
              type="button"
              className="auth-link-button"
              onClick={handleResend}
              disabled={cooldown > 0 || resending || loading || verified}
            >
              {resending
                ? 'Sending...'
                : cooldown > 0
                  ? `Resend code in ${cooldown}s`
                  : 'Resend code'}
            </button>

            <button
              type="button"
              className="auth-link-button"
              onClick={backToForm}
              disabled={loading || verified}
            >
              Use a different email
            </button>
          </div>

          <p className="auth-footer">
            Already verified?{' '}
            <Link to="/login">Login</Link>
          </p>

        </div>
      </div>
    );
  }

  // ── Render: step 1 ────────────────────────────────────────────────────────
  return (
    <div className="auth-page">
      <div className="auth-card">

        <h1 className="auth-title">Create Account </h1>
        <p className="auth-subtitle">Start your fitness journey today</p>

        {/* ✅ Error Message */}
        {error && (
          <div className="auth-error">
             {error}
          </div>
        )}

        {/* ✅ ADDED: Success Message */}
        {success && (
          <div className="auth-success">
             {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">

          <div className="form-group">
            <label className="form-label" htmlFor="signup-email">Email</label>
            <input
              id="signup-email"
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              autoComplete="email"            // ✅ ADDED
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="signup-password">Password</label>
            <input
              id="signup-password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Create a password (min 6 chars)"
              autoComplete="new-password"     // ✅ ADDED
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="signup-confirm">Confirm Password</label>
            <input
              id="signup-confirm"
              type="password"
              className="form-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm your password"
              autoComplete="new-password"     // ✅ ADDED
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={loading || !!success}   // ✅ disable after success too
          >
            {loading ? (
              <>
                <span className="btn-spinner"></span>
                Creating Account...
              </>
            ) : (
              'Sign Up'
            )}
          </button>

        </form>

        <div className="auth-actions">
          <button
            type="button"
            className="auth-link-button"
            onClick={openVerifyStep}
            disabled={loading || !!success}
          >
            Already have a verification code?
          </button>
        </div>

        <p className="auth-footer">
          Already have an account?{' '}
          <Link to="/login">Login</Link>
        </p>

      </div>
    </div>
  );
};

export default Signup;
