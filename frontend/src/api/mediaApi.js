/**
 * Media API functions — all backend calls related to media files.
 */

import apiClient from './axiosInstance';

/**
 * Register uploaded file metadata and enqueue processing.
 * @param {Object} payload - { file_name, storage_path, file_size_bytes, mime_type }
 * @returns {Promise<{ message: string, file_id: string }>}
 */
export const uploadMedia = async (payload) => {
  const response = await apiClient.post('/media/upload', payload);
  return response.data;
};

/**
 * List all media files for the current user (paginated).
 * @param {number} page - Page number (1-indexed)
 * @param {number} perPage - Items per page
 * @returns {Promise<{ items: MediaFile[], total: number, page: number, pages: number }>}
 */
export const listMediaFiles = async (page = 1, perPage = 20) => {
  const response = await apiClient.get('/media/', { params: { page, per_page: perPage } });
  return response.data;
};

/**
 * Get details and status for a single media file.
 * @param {string} fileId - UUID of the media file
 * @returns {Promise<MediaFile>}
 */
export const getMediaFile = async (fileId) => {
  const response = await apiClient.get(`/media/${fileId}`);
  return response.data;
};

/**
 * Delete a media file and all associated data.
 * @param {string} fileId - UUID of the media file
 * @returns {Promise<{ message: string }>}
 */
export const deleteMediaFile = async (fileId) => {
  const response = await apiClient.delete(`/media/${fileId}`);
  return response.data;
};

/**
 * Fetch the transcript for a completed media file.
 * @param {string} fileId - UUID of the media file
 * @returns {Promise<Transcript>}
 */
export const getTranscript = async (fileId) => {
  const response = await apiClient.get(`/media/${fileId}/transcript`);
  return response.data;
};

/**
 * Fetch the AI-generated summary for a completed media file.
 * @param {string} fileId - UUID of the media file
 * @returns {Promise<Summary>}
 */
export const getSummary = async (fileId) => {
  const response = await apiClient.get(`/media/${fileId}/summary`);
  return response.data;
};

/**
 * Retry processing for a failed media file.
 * @param {string} fileId - UUID of the media file
 * @returns {Promise<{ message: string }>}
 */
export const retryProcessing = async (fileId) => {
  const response = await apiClient.post(`/media/${fileId}/retry`);
  return response.data;
};
