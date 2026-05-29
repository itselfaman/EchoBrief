import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../store/authContext.jsx';

export default function Navbar() {
  const { user, signOut } = useAuth();
  const location = useLocation();

  const handleSignOut = async () => {
    // Do NOT call navigate() here — signOut() updates the Supabase session,
    // which fires onAuthStateChange → sets session=null → ProtectedRoute
    // renders <Navigate to="/auth" replace /> declaratively.
    //
    // Calling navigate('/auth') imperatively at the same time created a
    // double-navigation race: two pushes to the history stack in the same tick,
    // causing a redirect loop on the next render cycle.
    await signOut();
  };

  return (
    <>
      <style>{`
        .navbar {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 100;
          height: 64px;
          display: flex;
          align-items: center;
          padding: 0 var(--space-6);
          background: rgba(10, 10, 15, 0.85);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border-bottom: 1px solid var(--color-border);
        }

        .navbar-inner {
          width: 100%;
          max-width: 1280px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .navbar-brand {
          display: flex;
          align-items: center;
          gap: 10px;
          text-decoration: none;
          color: inherit;
        }

        .navbar-logo {
          width: 34px;
          height: 34px;
          background: var(--gradient-brand);
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1rem;
          box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);
          transition: box-shadow var(--transition-base);
        }

        .navbar-brand:hover .navbar-logo {
          box-shadow: 0 4px 16px rgba(124, 58, 237, 0.6);
        }

        .navbar-title {
          font-size: 1.2rem;
          font-weight: 800;
          letter-spacing: -0.03em;
          background: var(--gradient-brand);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .navbar-right {
          display: flex;
          align-items: center;
          gap: var(--space-4);
        }

        .navbar-user {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          padding: 6px 12px;
          background: var(--glass-bg);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-full);
        }

        .navbar-avatar {
          width: 28px;
          height: 28px;
          background: var(--gradient-brand);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.75rem;
          font-weight: 700;
          color: white;
          flex-shrink: 0;
        }

        .navbar-email {
          font-size: 0.8rem;
          color: var(--color-text-secondary);
          max-width: 180px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .navbar-signout {
          padding: 6px 14px;
          background: transparent;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          color: var(--color-text-muted);
          font-family: var(--font-sans);
          font-size: 0.8rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .navbar-signout:hover {
          border-color: rgba(239, 68, 68, 0.4);
          color: #fca5a5;
          background: rgba(239, 68, 68, 0.08);
        }

        @media (max-width: 640px) {
          .navbar-email { display: none; }
          .navbar { padding: 0 var(--space-4); }
        }
      `}</style>

      <nav className="navbar" role="navigation" aria-label="Main navigation">
        <div className="navbar-inner">
          <Link to="/dashboard" className="navbar-brand" aria-label="EchoBrief Home">
            <div className="navbar-logo">🎙️</div>
            <span className="navbar-title">EchoBrief</span>
          </Link>

          <div className="navbar-right">
            {user && (
              <div className="navbar-user" aria-label="User information">
                <div className="navbar-avatar" aria-hidden="true">
                  {(user.email || '?')[0].toUpperCase()}
                </div>
                <span className="navbar-email">{user.email}</span>
              </div>
            )}
            <button
              id="navbar-signout-btn"
              className="navbar-signout"
              onClick={handleSignOut}
              aria-label="Sign out"
            >
              Sign Out
            </button>
          </div>
        </div>
      </nav>
    </>
  );
}
