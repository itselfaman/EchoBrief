import React from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import StatusBadge from '../StatusBadge/StatusBadge.jsx';
import { deleteMediaFile } from '../../api/mediaApi.js';

function formatBytes(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

const FILE_ICON = {
  mp3: '🎵', wav: '🎵', ogg: '🎵', flac: '🎵', m4a: '🎵', aac: '🎵',
  mp4: '🎬', mov: '🎬', avi: '🎬', mkv: '🎬', webm: '🎬', mpeg: '🎬',
};

function getFileIcon(filename) {
  const ext = (filename || '').split('.').pop().toLowerCase();
  return FILE_ICON[ext] || '📁';
}

/**
 * MediaCard — displays a single media file record in the dashboard grid.
 *
 * @param {{ id, file_name, file_size_bytes, status, created_at, error_message }} file
 */
export default function MediaCard({ file }) {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => deleteMediaFile(file.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media-files'] });
    },
  });

  const handleDelete = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`Delete "${file.file_name}"? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  const isClickable = file.status === 'completed';

  const CardContent = (
    <>
      <style>{`
        .media-card {
          background: var(--glass-bg);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--space-5);
          transition: all var(--transition-base);
          position: relative;
          animation: fadeIn 0.4s ease both;
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          text-decoration: none;
          color: inherit;
        }

        .media-card:hover {
          border-color: rgba(124, 58, 237, 0.35);
          box-shadow: var(--shadow-brand);
          transform: translateY(-2px);
        }

        .media-card--clickable { cursor: pointer; }
        .media-card--disabled  { cursor: default; }

        .media-card-header {
          display: flex;
          align-items: flex-start;
          gap: var(--space-3);
        }

        .media-card-icon {
          font-size: 1.8rem;
          flex-shrink: 0;
          line-height: 1;
          filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }

        .media-card-title {
          flex: 1;
          min-width: 0;
        }

        .media-card-name {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--color-text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          line-height: 1.3;
        }

        .media-card-meta {
          font-size: 0.75rem;
          color: var(--color-text-muted);
          margin-top: 3px;
        }

        .media-card-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-top: var(--space-3);
          border-top: 1px solid var(--color-border);
        }

        .media-card-date {
          font-size: 0.75rem;
          color: var(--color-text-muted);
        }

        .media-card-actions {
          display: flex;
          gap: var(--space-2);
          align-items: center;
        }

        .media-card-error {
          padding: 8px 12px;
          background: rgba(239, 68, 68, 0.08);
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: var(--radius-sm);
          font-size: 0.75rem;
          color: #fca5a5;
          word-break: break-word;
        }

        .media-card-view-btn {
          padding: 5px 12px;
          font-size: 0.75rem;
          background: rgba(124, 58, 237, 0.15);
          border: 1px solid rgba(124, 58, 237, 0.3);
          border-radius: var(--radius-sm);
          color: var(--color-brand-light);
          font-family: var(--font-sans);
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
          text-decoration: none;
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }

        .media-card-view-btn:hover {
          background: rgba(124, 58, 237, 0.25);
          border-color: rgba(124, 58, 237, 0.5);
        }

        .media-card-delete-btn {
          padding: 5px 8px;
          background: transparent;
          border: 1px solid transparent;
          border-radius: var(--radius-sm);
          color: var(--color-text-muted);
          font-family: var(--font-sans);
          font-size: 0.75rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .media-card-delete-btn:hover {
          background: rgba(239, 68, 68, 0.1);
          border-color: rgba(239, 68, 68, 0.3);
          color: #fca5a5;
        }

        .media-card-delete-btn:disabled { opacity: 0.4; cursor: not-allowed; }
      `}</style>

      <div className="media-card-header">
        <span className="media-card-icon" aria-hidden="true">
          {getFileIcon(file.file_name)}
        </span>
        <div className="media-card-title">
          <div className="media-card-name" title={file.file_name}>
            {file.file_name}
          </div>
          <div className="media-card-meta">{formatBytes(file.file_size_bytes)}</div>
        </div>
        <StatusBadge status={file.status} />
      </div>

      {file.status === 'failed' && file.error_message && (
        <div className="media-card-error" role="alert">
          ⚠️ {file.error_message}
        </div>
      )}

      <div className="media-card-footer">
        <span className="media-card-date">{formatDate(file.created_at)}</span>
        <div className="media-card-actions">
          {file.status === 'completed' && (
            <Link
              to={`/media/${file.id}`}
              className="media-card-view-btn"
              aria-label={`View results for ${file.file_name}`}
              onClick={(e) => e.stopPropagation()}
            >
              View Results →
            </Link>
          )}
          <button
            className="media-card-delete-btn"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            aria-label={`Delete ${file.file_name}`}
            title="Delete file"
          >
            {deleteMutation.isPending ? '…' : '🗑️'}
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div
      className={`media-card ${isClickable ? 'media-card--clickable' : 'media-card--disabled'}`}
      role="article"
      aria-label={`Media file: ${file.file_name}, status: ${file.status}`}
    >
      {CardContent}
    </div>
  );
}
