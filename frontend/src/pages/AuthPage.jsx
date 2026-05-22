import React, { useState } from 'react';
import { supabase } from '../supabaseClient';
import styles from './AuthPage.module.css';

const TABS = ['signin', 'signup'];

export default function AuthPage() {
  const [tab, setTab] = useState('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null); // { type: 'success'|'error', text: '' }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      if (tab === 'signin') {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setMessage({ type: 'success', text: 'Account created! Check your email to confirm.' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleMagicLink = async () => {
    if (!email) {
      setMessage({ type: 'error', text: 'Enter your email address first.' });
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const { error } = await supabase.auth.signInWithOtp({ email });
      if (error) throw error;
      setMessage({ type: 'success', text: 'Magic link sent! Check your inbox.' });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <style>{`
        .auth-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: var(--space-6);
          background-color: var(--color-bg-primary);
          background-image:
            radial-gradient(ellipse 80% 50% at 50% -10%, rgba(124, 58, 237, 0.2) 0%, transparent 70%),
            radial-gradient(ellipse 50% 40% at 80% 90%, rgba(6, 182, 212, 0.08) 0%, transparent 70%);
        }

        .auth-container {
          width: 100%;
          max-width: 420px;
          animation: slideUp 0.5s ease both;
        }

        .auth-brand {
          text-align: center;
          margin-bottom: var(--space-8);
        }

        .auth-logo {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          margin-bottom: var(--space-4);
        }

        .auth-logo-icon {
          width: 44px;
          height: 44px;
          background: var(--gradient-brand);
          border-radius: var(--radius-md);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.3rem;
          box-shadow: var(--shadow-brand);
        }

        .auth-logo-text {
          font-size: 1.6rem;
          font-weight: 800;
          letter-spacing: -0.03em;
        }

        .auth-tagline {
          font-size: 0.95rem;
          color: var(--color-text-muted);
        }

        .auth-card {
          background: var(--glass-bg);
          backdrop-filter: blur(20px);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-xl);
          padding: var(--space-8);
          box-shadow: var(--shadow-lg);
        }

        .auth-tabs {
          display: flex;
          background: rgba(255,255,255,0.04);
          border-radius: var(--radius-md);
          padding: 4px;
          margin-bottom: var(--space-8);
          gap: 4px;
        }

        .auth-tab {
          flex: 1;
          padding: 8px;
          border: none;
          border-radius: calc(var(--radius-md) - 2px);
          background: transparent;
          color: var(--color-text-muted);
          font-family: var(--font-sans);
          font-size: 0.875rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-base);
        }

        .auth-tab.active {
          background: var(--gradient-brand);
          color: white;
          box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);
        }

        .auth-form { display: flex; flex-direction: column; gap: var(--space-5); }

        .auth-field { display: flex; flex-direction: column; gap: var(--space-2); }

        .auth-message {
          padding: 12px 16px;
          border-radius: var(--radius-md);
          font-size: 0.875rem;
          font-weight: 500;
          animation: fadeIn 0.3s ease;
        }

        .auth-message.success {
          background: rgba(16, 185, 129, 0.1);
          border: 1px solid rgba(16, 185, 129, 0.3);
          color: #6ee7b7;
        }

        .auth-message.error {
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.3);
          color: #fca5a5;
        }

        .auth-divider {
          display: flex;
          align-items: center;
          gap: var(--space-4);
          color: var(--color-text-muted);
          font-size: 0.8rem;
        }

        .auth-divider::before, .auth-divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: var(--color-border);
        }
      `}</style>

      <div className="auth-container">
        {/* Brand */}
        <div className="auth-brand animate-fade-in">
          <div className="auth-logo">
            <div className="auth-logo-icon">🎙️</div>
            <span className="auth-logo-text gradient-text">EchoBrief</span>
          </div>
          <p className="auth-tagline">AI-powered media transcription & intelligence</p>
        </div>

        {/* Card */}
        <div className="auth-card animate-slide-up">
          {/* Tabs */}
          <div className="auth-tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                className={`auth-tab ${tab === t ? 'active' : ''}`}
                onClick={() => { setTab(t); setMessage(null); }}
              >
                {t === 'signin' ? 'Sign In' : 'Sign Up'}
              </button>
            ))}
          </div>

          {/* Form */}
          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-field">
              <label className="label" htmlFor="auth-email">Email Address</label>
              <input
                id="auth-email"
                className="input"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="auth-field">
              <label className="label" htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                className="input"
                type="password"
                placeholder={tab === 'signup' ? 'At least 8 characters' : '••••••••'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={tab === 'signup' ? 8 : 1}
                autoComplete={tab === 'signin' ? 'current-password' : 'new-password'}
              />
            </div>

            {message && (
              <div className={`auth-message ${message.type}`} role="alert">
                {message.text}
              </div>
            )}

            <button
              id="auth-submit-btn"
              type="submit"
              className="btn btn-primary btn-lg"
              disabled={loading}
            >
              {loading ? <span className="spinner" /> : null}
              {tab === 'signin' ? 'Sign In' : 'Create Account'}
            </button>

            <div className="auth-divider">or</div>

            <button
              id="auth-magic-link-btn"
              type="button"
              className="btn btn-secondary"
              onClick={handleMagicLink}
              disabled={loading}
            >
              ✉️ Send Magic Link
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
