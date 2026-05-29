import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase, STORAGE_BUCKET } from '../../supabaseClient.js';
import { uploadMedia } from '../../api/mediaApi.js';
import { useAuth } from '../../store/authContext.jsx';

const MAX_SIZE = 50 * 1024 * 1024; // 50MB
const ACCEPTED_TYPES = {
  'audio/*': ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.webm'],
  'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.mpeg', '.3gp'],
};

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

/**
 * UploadZone — drag-and-drop file upload component.
 *
 * Upload flow:
 * 1. User drops file onto this zone
 * 2. File is uploaded directly to Supabase Storage
 * 3. Metadata is POSTed to FastAPI backend → job enqueued
 * 4. Query cache is invalidated → dashboard refreshes
 */
export default function UploadZone() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadPhase, setUploadPhase] = useState(null); // 'uploading' | 'registering' | null
  const [error, setError] = useState(null);

  const registerMutation = useMutation({
    mutationFn: uploadMedia,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media-files'] });
    },
  });

  const processFile = useCallback(async (file) => {
    setError(null);
    setUploadProgress(0);
    setUploadPhase('uploading');

    try {
      // ── 1. Upload directly to Supabase Storage ─────────────────────────────
      const fileExt = file.name.split('.').pop();
      const storageKey = `${user.id}/${Date.now()}-${Math.random().toString(36).slice(2)}.${fileExt}`;

      const { error: storageError } = await supabase.storage
        .from(STORAGE_BUCKET)
        .upload(storageKey, file, {
          cacheControl: '3600',
          upsert: false,
          onUploadProgress: (progress) => {
            setUploadProgress(Math.round((progress.loaded / progress.total) * 100));
          },
        });

      if (storageError) throw storageError;

      // ── 2. Register with backend → enqueue worker ──────────────────────────
      setUploadPhase('registering');
      await registerMutation.mutateAsync({
        file_name: file.name,
        storage_path: storageKey,
        file_size_bytes: file.size,
        mime_type: file.type,
      });

      setUploadPhase(null);
      setUploadProgress(0);
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.');
      setUploadPhase(null);
      setUploadProgress(0);
    }
  }, [user, registerMutation]);

  const { getRootProps, getInputProps, isDragActive, isDragReject, fileRejections } = useDropzone({
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) processFile(acceptedFiles[0]);
    },
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE,
    maxFiles: 1,
    disabled: !!uploadPhase,
  });

  const isUploading = !!uploadPhase;

  return (
    <>
      <style>{`
        .upload-zone {
          position: relative;
          border: 2px dashed var(--color-border);
          border-radius: var(--radius-xl);
          padding: var(--space-12) var(--space-8);
          text-align: center;
          cursor: pointer;
          transition: all var(--transition-base);
          background: var(--gradient-card);
          overflow: hidden;
        }

        .upload-zone:hover:not(.upload-zone--disabled) {
          border-color: var(--color-brand-primary);
          background: rgba(124, 58, 237, 0.06);
          box-shadow: var(--shadow-brand);
        }

        .upload-zone--active {
          border-color: var(--color-brand-primary) !important;
          background: rgba(124, 58, 237, 0.1) !important;
          box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.15), var(--shadow-brand);
        }

        .upload-zone--reject {
          border-color: var(--color-danger) !important;
          background: rgba(239, 68, 68, 0.05) !important;
        }

        .upload-zone--disabled {
          cursor: not-allowed;
          opacity: 0.8;
        }

        .upload-icon {
          font-size: 3rem;
          margin-bottom: var(--space-4);
          display: block;
          transition: transform var(--transition-base);
        }

        .upload-zone:hover:not(.upload-zone--disabled) .upload-icon {
          transform: translateY(-4px) scale(1.1);
        }

        .upload-zone--active .upload-icon {
          transform: translateY(-6px) scale(1.15);
          animation: bounce 0.6s ease infinite alternate;
        }

        @keyframes bounce {
          from { transform: translateY(-4px) scale(1.1); }
          to   { transform: translateY(-8px) scale(1.15); }
        }

        .upload-title {
          font-size: 1.1rem;
          font-weight: 700;
          color: var(--color-text-primary);
          margin-bottom: var(--space-2);
        }

        .upload-subtitle {
          font-size: 0.875rem;
          color: var(--color-text-muted);
          margin-bottom: var(--space-6);
        }

        .upload-types {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
          justify-content: center;
          margin-top: var(--space-4);
        }

        .upload-type-tag {
          padding: 3px 10px;
          background: rgba(124, 58, 237, 0.1);
          border: 1px solid rgba(124, 58, 237, 0.2);
          border-radius: var(--radius-full);
          font-size: 0.7rem;
          font-weight: 600;
          color: var(--color-brand-light);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .upload-progress-container {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          padding: var(--space-4);
        }

        .upload-progress-bar-track {
          width: 100%;
          height: 6px;
          background: rgba(255,255,255,0.08);
          border-radius: 3px;
          overflow: hidden;
        }

        .upload-progress-bar-fill {
          height: 100%;
          background: var(--gradient-brand);
          border-radius: 3px;
          transition: width 0.2s ease;
          box-shadow: 0 0 8px rgba(124, 58, 237, 0.5);
        }

        .upload-phase-text {
          font-size: 0.875rem;
          color: var(--color-brand-light);
          font-weight: 600;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-2);
        }

        .upload-error {
          margin-top: var(--space-4);
          padding: 12px 16px;
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: var(--radius-md);
          color: #fca5a5;
          font-size: 0.875rem;
          font-weight: 500;
          text-align: left;
        }
      `}</style>

      <div>
        <div
          {...getRootProps({
            className: [
              'upload-zone',
              isDragActive && !isDragReject ? 'upload-zone--active' : '',
              isDragReject ? 'upload-zone--reject' : '',
              isUploading ? 'upload-zone--disabled' : '',
            ].filter(Boolean).join(' '),
            id: 'upload-dropzone',
            'aria-label': 'Upload audio or video file',
          })}
        >
          <input {...getInputProps()} id="upload-file-input" />

          {isUploading ? (
            <div className="upload-progress-container">
              <span className="upload-icon">🚀</span>
              <div className="upload-phase-text">
                <span className="spinner" />
                {uploadPhase === 'uploading'
                  ? `Uploading to storage… ${uploadProgress}%`
                  : 'Registering & queuing for AI processing…'}
              </div>
              {uploadPhase === 'uploading' && (
                <div className="upload-progress-bar-track">
                  <div
                    className="upload-progress-bar-fill"
                    style={{ width: `${uploadProgress}%` }}
                    role="progressbar"
                    aria-valuenow={uploadProgress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  />
                </div>
              )}
            </div>
          ) : (
            <>
              <span className="upload-icon" aria-hidden="true">
                {isDragReject ? '🚫' : isDragActive ? '📂' : '🎙️'}
              </span>
              <p className="upload-title">
                {isDragReject
                  ? 'File type not supported'
                  : isDragActive
                  ? 'Drop it!'
                  : 'Drop your audio or video file here'}
              </p>
              <p className="upload-subtitle">
                or click to browse — up to 50 MB
              </p>
              <button type="button" className="btn btn-primary" tabIndex={-1}>
                Choose File
              </button>
              <div className="upload-types" aria-label="Supported file types">
                {['MP3', 'MP4', 'WAV', 'MOV', 'M4A', 'MKV', 'OGG', 'FLAC'].map(ext => (
                  <span key={ext} className="upload-type-tag">{ext}</span>
                ))}
              </div>
            </>
          )}
        </div>

        {error && (
          <div className="upload-error" role="alert">⚠️ {error}</div>
        )}

        {fileRejections.length > 0 && !error && (
          <div className="upload-error" role="alert">
            ⚠️ {fileRejections[0]?.errors?.[0]?.message || 'File rejected'}
          </div>
        )}
      </div>
    </>
  );
}
