import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import html2pdf from 'html2pdf.js';
import { getMediaFile, getTranscript, getSummary, retryProcessing } from '../api/mediaApi.js';
import StatusBadge from '../components/StatusBadge/StatusBadge.jsx';

const TABS = [
  { id: 'summary', label: '✨ Summary' },
  { id: 'transcript', label: '📄 Transcript' },
];

const formatDuration = (seconds) => {
  if (!seconds) return '';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
};

export default function ResultPage() {
  const { fileId } = useParams();
  const [activeTab, setActiveTab] = useState('summary');
  const [isRetrying, setIsRetrying] = useState(false);

  const fileQuery = useQuery({
    queryKey: ['media-file', fileId],
    queryFn: () => getMediaFile(fileId),
    refetchInterval: (data) =>
      data?.status === 'processing' || data?.status === 'pending' ? 4000 : false,
  });

  const summaryQuery = useQuery({
    queryKey: ['summary', fileId],
    queryFn: () => getSummary(fileId),
    enabled: fileQuery.data?.status === 'completed',
  });

  const transcriptQuery = useQuery({
    queryKey: ['transcript', fileId],
    queryFn: () => getTranscript(fileId),
    enabled: fileQuery.data?.status === 'completed' && activeTab === 'transcript',
  });

  const file = fileQuery.data;
  const summary = summaryQuery.data;
  const transcript = transcriptQuery.data;

  const handleRetry = async () => {
    try {
      setIsRetrying(true);
      await retryProcessing(fileId);
      fileQuery.refetch();
    } catch (err) {
      alert('Failed to retry: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsRetrying(false);
    }
  };

  const handleExportPDF = () => {
    const element = document.getElementById('summary-content');
    if (!element) return;
    const opt = {
      margin:       0.5,
      filename:     `${file?.file_name || 'Summary'}.pdf`,
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { scale: 2, useCORS: true },
      jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save();
  };

  const handleExportTXT = () => {
    if (!transcript?.raw_text) return;
    const element = document.createElement("a");
    const fileBlob = new Blob([transcript.raw_text], {type: 'text/plain'});
    element.href = URL.createObjectURL(fileBlob);
    element.download = `${file?.file_name || 'Transcript'}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <>
      <style>{`
        .result-page {
          max-width: 1100px;
          margin: 0 auto;
          padding: var(--space-8) var(--space-6);
        }

        .result-back {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 0.875rem;
          color: var(--color-text-muted);
          text-decoration: none;
          margin-bottom: var(--space-6);
          transition: color var(--transition-fast);
        }
        .result-back:hover { color: var(--color-text-primary); }

        .result-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: var(--space-4);
          margin-bottom: var(--space-8);
          animation: slideUp 0.4s ease;
          flex-wrap: wrap;
        }

        .result-title {
          font-size: clamp(1.25rem, 2.5vw, 1.75rem);
          font-weight: 800;
          letter-spacing: -0.02em;
          word-break: break-word;
        }

        .result-tabs {
          display: flex;
          background: rgba(255,255,255,0.04);
          border-radius: var(--radius-md);
          padding: 4px;
          gap: 4px;
          margin-bottom: var(--space-8);
          width: fit-content;
          animation: fadeIn 0.4s ease 0.1s both;
        }

        .result-tab {
          padding: 9px 20px;
          border: none;
          border-radius: calc(var(--radius-md) - 2px);
          background: transparent;
          color: var(--color-text-muted);
          font-family: var(--font-sans);
          font-size: 0.9rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-base);
          white-space: nowrap;
        }

        .result-tab.active {
          background: var(--gradient-brand);
          color: white;
          box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);
        }

        /* ── Summary Section ── */
        .summary-executive {
          background: var(--glass-bg);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--space-6);
          margin-bottom: var(--space-6);
          animation: fadeIn 0.4s ease both;
          line-height: 1.8;
          color: var(--color-text-secondary);
          font-size: 0.95rem;
        }

        .summary-section-title {
          font-size: 0.7rem;
          font-weight: 700;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--color-brand-light);
          margin-bottom: var(--space-4);
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }

        .summary-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--space-6);
        }

        .summary-card {
          background: var(--glass-bg);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--space-5);
          animation: fadeIn 0.4s ease both;
        }

        .takeaways-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .takeaway-item {
          display: flex;
          gap: var(--space-3);
          align-items: flex-start;
          padding: var(--space-3);
          background: rgba(255,255,255,0.03);
          border-radius: var(--radius-md);
          border: 1px solid rgba(255,255,255,0.05);
          transition: border-color var(--transition-fast);
        }

        .takeaway-item:hover { border-color: rgba(124, 58, 237, 0.2); }

        .takeaway-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          flex-shrink: 0;
          margin-top: 6px;
        }

        .takeaway-dot-insight    { background: var(--color-brand-light); }
        .takeaway-dot-decision   { background: var(--color-success); }
        .takeaway-dot-risk       { background: var(--color-danger); }
        .takeaway-dot-opportunity { background: var(--color-accent); }

        .takeaway-text {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
          line-height: 1.5;
        }

        .action-items-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .action-item {
          padding: var(--space-3) var(--space-4);
          border-radius: var(--radius-md);
          border: 1px solid rgba(255,255,255,0.06);
          background: rgba(255,255,255,0.02);
        }

        .action-item-task {
          font-size: 0.875rem;
          font-weight: 600;
          color: var(--color-text-primary);
          margin-bottom: 4px;
        }

        .action-item-meta {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          font-size: 0.75rem;
        }

        .action-owner {
          color: var(--color-text-muted);
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .priority-high   { color: #fca5a5; }
        .priority-medium { color: #fcd34d; }
        .priority-low    { color: #6ee7b7; }

        /* ── Transcript Section ── */
        .transcript-box {
          background: var(--glass-bg);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--space-6);
          animation: fadeIn 0.4s ease both;
          max-height: 600px;
          overflow-y: auto;
          font-size: 0.9rem;
          line-height: 1.9;
          color: var(--color-text-secondary);
          white-space: pre-wrap;
          word-break: break-word;
        }

        /* ── Processing States ── */
        .result-processing {
          text-align: center;
          padding: var(--space-16) var(--space-8);
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-4);
        }

        .result-processing-icon {
          font-size: 3.5rem;
          animation: spin 3s linear infinite;
        }

        .result-processing-title {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--color-text-secondary);
        }

        .result-processing-sub {
          font-size: 0.875rem;
          color: var(--color-text-muted);
        }

        @media (max-width: 768px) {
          .summary-grid { grid-template-columns: 1fr; }
          .result-page  { padding: var(--space-6) var(--space-4); }
        }
      `}</style>

      <div className="result-page">
        {/* Back */}
        <Link to="/dashboard" className="result-back" id="result-back-btn">
          ← Back to Dashboard
        </Link>

        {/* Header */}
        {fileQuery.isLoading ? (
          <div className="skeleton" style={{ height: 80, borderRadius: 'var(--radius-lg)', marginBottom: 'var(--space-8)' }} />
        ) : file ? (
          <div className="result-header">
            <div>
              <h1 className="result-title">{file.file_name}</h1>
              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: 6 }}>
                {new Date(file.created_at).toLocaleDateString('en-US', {
                  year: 'numeric', month: 'long', day: 'numeric'
                })}
                {file.audio_duration_seconds && ` • ${formatDuration(file.audio_duration_seconds)}`}
              </p>
            </div>
            <StatusBadge status={file.status} />
          </div>
        ) : null}

        {/* Processing / Failed States */}
        {file?.status === 'pending' || file?.status === 'processing' ? (
          <div className="result-processing">
            <div className="result-processing-icon" aria-hidden="true">⚙️</div>
            <div className="result-processing-title">
              {file.status === 'pending' ? 'Queued for processing…' : (file.processing_message || 'AI is working its magic…')}
            </div>
            <div className="result-processing-sub">
              This page will update automatically. Grab a coffee ☕
            </div>
            <div className="spinner" style={{ width: 32, height: 32, marginTop: 8 }} />
          </div>
        ) : file?.status === 'failed' ? (
          <div className="dashboard-error" style={{ marginTop: 'var(--space-4)', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 'var(--space-4)' }}>
            <div>⚠️ Processing failed: {file.error_message || 'Unknown error'}</div>
            <button className="btn-primary" onClick={handleRetry} disabled={isRetrying}>
              {isRetrying ? 'Retrying...' : 'Retry Processing'}
            </button>
          </div>
        ) : file?.status === 'completed' ? (
          <>
            {/* Tabs */}
            <div className="result-tabs" role="tablist" aria-label="Result sections">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  className={`result-tab ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                  id={`result-tab-${tab.id}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Summary Tab */}
            {activeTab === 'summary' && (
              summaryQuery.isLoading ? (
                <div className="skeleton" style={{ height: 300, borderRadius: 'var(--radius-lg)' }} />
              ) : summary ? (
                summary.executive_summary === "No speech detected in the uploaded audio." ? (
                  <div className="summary-executive" style={{ textAlign: 'center', padding: 'var(--space-12) var(--space-6)', border: '2px dashed rgba(255,255,255,0.1)' }}>
                    <div style={{ fontSize: '3rem', marginBottom: 'var(--space-4)' }}>🤫</div>
                    <h2 style={{ color: 'var(--color-text-primary)', marginBottom: 'var(--space-2)' }}>No Speech Detected</h2>
                    <p style={{ color: 'var(--color-text-muted)' }}>We couldn't detect enough speech in this audio file to generate a summary.</p>
                  </div>
                ) : (
                  <div>
                    {/* Actions & Metrics */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                      <div className="summary-section-title" style={{ margin: 0 }}>✨ Executive Summary</div>
                      <button className="btn-secondary" onClick={handleExportPDF} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>Export PDF</button>
                    </div>

                    <div id="summary-content">
                      <div className="summary-executive">{summary.executive_summary}</div>

                      {/* Key Takeaways + Action Items */}
                      <div className="summary-grid">
                        {/* Key Takeaways */}
                        <div className="summary-card">
                          <div className="summary-section-title">💡 Key Takeaways</div>
                          <div className="takeaways-list">
                            {(summary.key_takeaways || []).map((item, i) => (
                              <div key={i} className="takeaway-item animate-fade-in" style={{ animationDelay: `${i * 0.05}s` }}>
                                <div className={`takeaway-dot takeaway-dot-${item.category || 'insight'}`} aria-hidden="true" />
                                <div className="takeaway-text">{item.point}</div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Action Items */}
                        <div className="summary-card">
                          <div className="summary-section-title">✅ Action Items</div>
                          <div className="action-items-list">
                            {(summary.action_items || []).map((item, i) => (
                              <div key={i} className="action-item animate-fade-in" style={{ animationDelay: `${i * 0.05}s` }}>
                                <div className="action-item-task">{item.task}</div>
                                <div className="action-item-meta">
                                  {item.owner && (
                                    <span className="action-owner">👤 {item.owner}</span>
                                  )}
                                  <span className={`priority-${item.priority || 'medium'}`}>
                                    {item.priority === 'high' ? '🔴' : item.priority === 'low' ? '🟢' : '🟡'} {item.priority || 'medium'}
                                  </span>
                                </div>
                              </div>
                            ))}
                            {(summary.action_items || []).length === 0 && (
                              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                                No action items identified.
                              </p>
                            )}
                          </div>
                        </div>
                      </div>

                      {summary.generation_time_sec && (
                        <div style={{ marginTop: 'var(--space-6)', fontSize: '0.8rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>
                          Generated in {summary.generation_time_sec}s
                        </div>
                      )}
                    </div>
                  </div>
                )
              ) : null
            )}

            {/* Transcript Tab */}
            {activeTab === 'transcript' && (
              transcriptQuery.isLoading ? (
                <div className="skeleton" style={{ height: 400, borderRadius: 'var(--radius-lg)' }} />
              ) : transcript ? (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                    <div className="summary-section-title" style={{ margin: 0 }}>
                      📄 Full Transcript {transcript.word_count && `(${transcript.word_count} words)`}
                    </div>
                    <button className="btn-secondary" onClick={handleExportTXT} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>Export TXT</button>
                  </div>
                  <div className="transcript-box" role="document" aria-label="Transcript content">
                    {transcript.raw_text}
                  </div>
                </div>
              ) : null
            )}
          </>
        ) : null}
      </div>
    </>
  );
}
