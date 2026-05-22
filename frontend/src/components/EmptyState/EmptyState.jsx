import React from 'react';

export default function EmptyState({ title = 'No files yet', description, action }) {
  return (
    <>
      <style>{`
        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          text-align: center;
          padding: var(--space-16) var(--space-8);
          gap: var(--space-4);
          animation: fadeIn 0.5s ease;
        }

        .empty-state-icon {
          font-size: 4rem;
          margin-bottom: var(--space-2);
          filter: grayscale(0.3);
          opacity: 0.8;
        }

        .empty-state-title {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--color-text-secondary);
        }

        .empty-state-desc {
          font-size: 0.9rem;
          color: var(--color-text-muted);
          max-width: 360px;
          line-height: 1.6;
        }
      `}</style>

      <div className="empty-state" role="status" aria-label={title}>
        <div className="empty-state-icon" aria-hidden="true">🎙️</div>
        <div className="empty-state-title">{title}</div>
        {description && <p className="empty-state-desc">{description}</p>}
        {action}
      </div>
    </>
  );
}
