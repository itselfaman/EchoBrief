/**
 * Axios instance pre-configured for EchoBrief API requests.
 *
 * Features:
 * - Base URL from environment variable
 * - Request interceptor: automatically attaches Supabase JWT as Bearer token
 * - Response interceptor: normalises error responses
 *
 * Axios is a production-grade, battle-tested HTTP client used by millions of
 * production applications. It provides clean interceptor support for JWT injection,
 * automatic JSON serialisation, and better error handling than raw fetch.
 */

import axios from 'axios';
import { supabase } from '../supabaseClient';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000, // 30 second timeout
});

// ── Request Interceptor — Attach JWT ──────────────────────────────────────────

apiClient.interceptors.request.use(
  async (config) => {
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response Interceptor — Normalize Errors ───────────────────────────────────

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const response = error.response;

    if (response?.status === 401) {
      // Token expired — sign out and redirect to auth page
      supabase.auth.signOut();
      window.location.href = '/auth';
      return Promise.reject(new Error('Session expired. Please sign in again.'));
    }

    // Extract structured error from our API error envelope
    const apiError = response?.data?.error;
    if (apiError) {
      const err = new Error(apiError.message || 'An unexpected error occurred.');
      err.code = apiError.code;
      err.field = apiError.field;
      err.status = response.status;
      return Promise.reject(err);
    }

    return Promise.reject(error);
  }
);

export default apiClient;
