import React from 'react';

const STATUS_CONFIG = {
  pending:    { label: 'Pending',    className: 'badge-pending',    dot: '⏳' },
  processing: { label: 'Processing', className: 'badge-processing', dot: null },
  completed:  { label: 'Completed',  className: 'badge-completed',  dot: '✓' },
  failed:     { label: 'Failed',     className: 'badge-failed',     dot: '✕' },
};

/**
 * StatusBadge — displays the current processing state of a media file.
 *
 * @param {string} status - One of: pending, processing, completed, failed
 */
export default function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;

  return (
    <span
      className={`badge ${config.className}`}
      role="status"
      aria-label={`Status: ${config.label}`}
    >
      {config.dot && <span aria-hidden="true">{config.dot}</span>}
      {config.label}
    </span>
  );
}
