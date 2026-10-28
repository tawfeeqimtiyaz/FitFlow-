import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

const Login = () => {
  // Coming from the verification step: prefill the email and confirm success
  const location = useLocation();

  const [email, setEmail]       = useState(location.state?.email || '');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [needsVerification, setNeedsVerification] = useState(false);
  const [loading, setLoading]   = useState(false);
  const justVerified = !!location.state?.verified;

  const { login, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  // ✅ ADDED: Redirect if already logged in
  useEffect(() => {
    if (!authLoading && user) {
      navigate('/dashboard', { replace: true });
    }
  }, [user, authLoading, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setNeedsVerification(false);
    setLoading(true);

    try {
      await login(email, password);
      navigate('/dashboard', { replace: true }); // ✅ replace: true prevents
    } catch (err) {                               //    back-button to login
      // 403 = correct password but the email has not been verified yet
      setNeedsVerification(err.response?.status === 403);
      setError(
        err.response?.data?.detail ||
        (err.response
          ? 'Login failed. Please check your credentials.'
          : 'Cannot reach the server. Please check your connection and try again.')
      );
    } finally {
      setLoading(false);
    }
  };

  // ✅ Don't flash login form while checking auth
  if (authLoading) return null;

  return (
    <div className="auth-page">
      <div className="auth-card">

        <h1 className="auth-title">Welcome Back </h1>
        <p className="auth-subtitle">Login to continue your fitness journey</p>

        {/* Shown right after the one-time code was accepted */}
        {justVerified && !error && (
          <div className="auth-success" role="status">
             Email verified! You can now log in.
          </div>
        )}

        {/* ✅ Error Message */}
        {error && (
          <div className="auth-error" role="alert">
             {error}
            {needsVerification && (
              <div className="auth-error-action">
                <Link to="/signup" state={{ verifyEmail: email }}>
                  Verify your email
                </Link>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">

          <div className="form-group">
            <label className="form-label" htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              autoComplete="email"           // ✅ ADDED: browser autofill
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password" // ✅ ADDED: browser autofill
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="btn-spinner"></span>
                Logging in...
              </>
            ) : (
              'Login'
            )}
          </button>

        </form>

        <p className="auth-footer">
          Don't have an account?{' '}
          <Link to="/signup">Sign Up</Link>
        </p>

      </div>
    </div>
  );
};

export default Login;