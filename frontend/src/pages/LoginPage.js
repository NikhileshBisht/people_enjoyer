import React, { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Mail, KeyRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

function MacnikLogo({ size = 'sm' }) {
  return (
    <div className={`macnik-logo macnik-logo-${size}`} aria-hidden="true">
      M
    </div>
  );
}

function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated, authLoading } = useAuth();
  const [mode, setMode] = useState('register');
  const [step, setStep] = useState('request');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  if (authLoading) {
    return <div className="login-loading-screen">Checking session...</div>;
  }

  if (isAuthenticated) {
    return <Navigate to="/macnik" replace />;
  }

  const resetStatus = () => {
    setError('');
    setMessage('');
  };

  const handleModeChange = (newMode) => {
    setMode(newMode);
    setStep('request');
    setOtp('');
    resetStatus();
  };

  const requestOtp = async () => {
    resetStatus();
    if (!email.trim()) {
      setError('Email is required.');
      return;
    }

    setLoading(true);
    try {
      const endpoint =
        mode === 'register' ? '/auth/register/request-otp' : '/auth/login/request-otp';
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data.detail;
        const errorMessage =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
            ? detail.map((item) => item.msg).join(', ')
            : 'Failed to send OTP.';
        throw new Error(errorMessage);
      }
      setMessage(data.message || 'OTP sent to your email.');
      setStep('verify');
    } catch (err) {
      setError(err.message || 'Failed to send OTP.');
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async () => {
    resetStatus();
    if (!otp.trim()) {
      setError('OTP is required.');
      return;
    }

    setLoading(true);
    try {
      const endpoint =
        mode === 'register' ? '/auth/register/verify-otp' : '/auth/login/verify-otp';
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase(), otp: otp.trim() }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'OTP verification failed.');
      }
      login(data.access_token);
      navigate('/macnik', { replace: true });
    } catch (err) {
      setError(err.message || 'OTP verification failed.');
    } finally {
      setLoading(false);
    }
  };

  const primaryLabel =
    step === 'request'
      ? loading
        ? 'Sending...'
        : mode === 'register'
        ? 'Send Registration OTP'
        : 'Send Login OTP'
      : loading
      ? 'Verifying...'
      : 'Verify OTP';

  return (
    <div className="login-page">
      <aside className="login-brand-panel">
        <div className="login-brand-content">
          <MacnikLogo size="lg" />
          <h1>MacNik</h1>
          <p>Simplify. Organize. Succeed. That&apos;s MacNik.</p>
        </div>
      </aside>

      <main className="login-form-panel">
        <div className="login-card">
          <div className="login-card-header">
            <div className="login-brand-name">
              <MacnikLogo size="sm" />
              <span>MacNik</span>
            </div>
            <h2>Welcome back!</h2>
            <p>Please sign in to continue</p>
          </div>

          <div className="login-mode-toggle">
            <button
              type="button"
              className={mode === 'register' ? 'active' : ''}
              onClick={() => handleModeChange('register')}
            >
              Register
            </button>
            <button
              type="button"
              className={mode === 'login' ? 'active' : ''}
              onClick={() => handleModeChange('login')}
            >
              Login
            </button>
          </div>

          <div className="login-field">
            <label htmlFor="email">Email</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">
                <Mail size={18} />
              </span>
              <input
                id="email"
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading || step === 'verify'}
              />
            </div>
          </div>

          {step === 'verify' && (
            <div className="login-field">
              <label htmlFor="otp">Enter OTP</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">
                  <KeyRound size={18} />
                </span>
                <input
                  id="otp"
                  type="text"
                  placeholder="6 digit OTP"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  disabled={loading}
                />
              </div>
              <button
                type="button"
                className="login-change-email"
                onClick={() => setStep('request')}
                disabled={loading}
              >
                Change email
              </button>
            </div>
          )}

          {error && <div className="login-alert login-alert-error">{error}</div>}
          {message && <div className="login-alert login-alert-success">{message}</div>}

          {step === 'request' ? (
            <button
              type="button"
              className="login-primary-btn"
              onClick={requestOtp}
              disabled={loading}
            >
              {primaryLabel}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="login-primary-btn"
                onClick={verifyOtp}
                disabled={loading}
              >
                {primaryLabel}
              </button>
              <button
                type="button"
                className="login-secondary-btn"
                onClick={() => setStep('request')}
                disabled={loading}
              >
                Change Email
              </button>
            </>
          )}

          <p className="login-footer">
            {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}
            <button
              type="button"
              onClick={() => handleModeChange(mode === 'login' ? 'register' : 'login')}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}

export default LoginPage;
