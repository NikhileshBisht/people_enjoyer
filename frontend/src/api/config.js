/**
 * api/config.js
 * Central configuration for all API calls.
 */

export const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

/**
 * A thin wrapper around fetch that:
 *  - Prepends the base URL
 *  - Sets JSON Content-Type by default
 *  - Attaches the Bearer token when provided
 *  - Throws an Error with the API's detail message on non-2xx responses
 *
 * @param {string} path        - e.g. '/auth/login/request-otp'
 * @param {object} [options]   - standard fetch options
 * @param {string} [token]     - JWT access token (optional)
 * @returns {Promise<any>}     - parsed JSON body
 */
export async function apiFetch(path, options = {}, token = null) {
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json();

  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
        ? detail.map((e) => e.msg).join(', ')
        : 'An unexpected error occurred.';
    throw new Error(message);
  }

  return data;
}
