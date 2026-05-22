import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import UploadZone from '../components/UploadZone/UploadZone.jsx';
import MediaCard from '../components/MediaCard/MediaCard.jsx';
import EmptyState from '../components/EmptyState/EmptyState.jsx';
import { listMediaFiles } from '../api/mediaApi.js';

const POLL_INTERVAL = 5000; // 5s — auto-refresh while any file is processing

export default function DashboardPage() {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['media-files', page],
    queryFn: () => listMediaFiles(page, 20),
    refetchInterval: (data) => {
      // Keep polling if any file is in a non-terminal state
      const hasActive = data?.items?.some(
        (f) => f.status === 'pending' || f.status === 'processing'
      );
      return hasActive ? POLL_INTERVAL : false;
    },
  });

  const files = data?.items || [];
  const totalPages = data?.pages || 1;

  return (
    <>
      <style>{`
        .dashboard {
          padding: var(--space-8) 0;
        }

        .dashboard-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 var(--space-6);
        }

        .dashboard-header {
          margin-bottom: var(--space-8);
          animation: slideUp 0.4s ease both;
        }

        .dashboard-title {
          font-size: clamp(1.75rem, 3vw, 2.5rem);
          font-weight: 800;
          letter-spacing: -0.03em;
          margin-bottom: var(--space-2);
        }

        .dashboard-subtitle {
          color: var(--color-text-muted);
          font-size: 1rem;
        }

        .dashboard-upload-section {
          margin-bottom: var(--space-10);
          animation: slideUp 0.5s ease both;
          animation-delay: 0.05s;
        }

        .dashboard-files-section {
          animation: slideUp 0.5s ease both;
          animation-delay: 0.1s;
        }

        .dashboard-files-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: var(--space-6);
        }

        .dashboard-section-title {
          font-size: 1.1rem;
          font-weight: 700;
          color: var(--color-text-primary);
          display: flex;
          align-items: center;
          gap: var(--space-3);
        }

        .dashboard-count {
          font-size: 0.75rem;
          padding: 2px 8px;
          background: rgba(124, 58, 237, 0.15);
          border-radius: var(--radius-full);
          color: var(--color-brand-light);
          font-weight: 700;
        }

        .dashboard-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
          gap: var(--space-5);
        }

        .dashboard-skeleton {
          height: 160px;
          border-radius: var(--radius-lg);
        }

        .dashboard-error {
          padding: var(--space-5) var(--space-6);
          background: rgba(239, 68, 68, 0.08);
          border: 1px solid rgba(239, 68, 68, 0.25);
          border-radius: var(--radius-lg);
          color: #fca5a5;
          font-size: 0.9rem;
        }

        .dashboard-pagination {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-3);
          margin-top: var(--space-8);
        }

        .dashboard-page-info {
          font-size: 0.875rem;
          color: var(--color-text-muted);
          font-weight: 500;
        }

        @media (max-width: 640px) {
          .dashboard-grid { grid-template-columns: 1fr; }
          .dashboard-container { padding: 0 var(--space-4); }
        }
      `}</style>

      <div className="dashboard">
        <div className="dashboard-container">
          {/* Header */}
          <div className="dashboard-header">
            <h1 className="dashboard-title">
              Your Media <span className="gradient-text">Intelligence</span>
            </h1>
            <p className="dashboard-subtitle">
              Upload recordings — get transcripts, summaries & action items instantly.
            </p>
          </div>

          {/* Upload Zone */}
          <div className="dashboard-upload-section">
            <UploadZone />
          </div>

          {/* Files List */}
          <div className="dashboard-files-section">
            <div className="dashboard-files-header">
              <div className="dashboard-section-title">
                Recent Files
                {data?.total > 0 && (
                  <span className="dashboard-count">{data.total}</span>
                )}
              </div>
            </div>

            {isLoading ? (
              <div className="dashboard-grid">
                {[1, 2, 3].map(i => (
                  <div key={i} className={`skeleton dashboard-skeleton stagger-${i}`} />
                ))}
              </div>
            ) : isError ? (
              <div className="dashboard-error" role="alert">
                ⚠️ Failed to load files: {error?.message || 'Unknown error'}
              </div>
            ) : files.length === 0 ? (
              <EmptyState
                title="No recordings yet"
                description="Upload your first audio or video file above to get AI-powered transcripts and summaries."
              />
            ) : (
              <>
                <div className="dashboard-grid" role="list" aria-label="Your media files">
                  {files.map((file, idx) => (
                    <div key={file.id} role="listitem">
                      <MediaCard file={file} />
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="dashboard-pagination" aria-label="Pagination">
                    <button
                      id="dashboard-prev-btn"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      aria-label="Previous page"
                    >
                      ← Prev
                    </button>
                    <span className="dashboard-page-info">
                      Page {page} of {totalPages}
                    </span>
                    <button
                      id="dashboard-next-btn"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      aria-label="Next page"
                    >
                      Next →
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
