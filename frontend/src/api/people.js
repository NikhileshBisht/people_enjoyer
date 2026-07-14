/**
 * api/people.js
 * People / connection endpoints.
 */

import { apiFetch } from './config';

/**
 * Fetch all pending incoming & outgoing connection requests for the viewer.
 * @param {string} token
 * @returns {Promise<{ incoming: object[], outgoing: object[] }>}
 */
export const getPeopleRequests = (token) =>
  apiFetch('/people/requests', {}, token);

/**
 * Send a connection request to another user.
 * @param {string} toEmail
 * @param {string} token
 * @returns {Promise<object>}
 */
export const sendPeopleRequest = (toEmail, token) =>
  apiFetch(
    '/people/requests',
    {
      method: 'POST',
      body: JSON.stringify({ to_email: toEmail }),
    },
    token
  );

/**
 * Accept a pending incoming connection request.
 * @param {string} requestId
 * @param {string} token
 * @returns {Promise<object>}
 */
export const acceptPeopleRequest = (requestId, token) =>
  apiFetch(
    `/people/requests/${requestId}/accept`,
    { method: 'POST' },
    token
  );

/**
 * Reject a pending incoming connection request.
 * @param {string} requestId
 * @param {string} token
 * @returns {Promise<object>}
 */
export const rejectPeopleRequest = (requestId, token) =>
  apiFetch(
    `/people/requests/${requestId}/reject`,
    { method: 'POST' },
    token
  );

/**
 * Cancel a pending outgoing connection request (sent by the viewer).
 * @param {string} requestId
 * @param {string} token
 * @returns {Promise<object>}
 */
export const cancelPeopleRequest = (requestId, token) =>
  apiFetch(
    `/people/requests/${requestId}`,
    { method: 'DELETE' },
    token
  );

/**
 * Remove an accepted connection with a partner.
 * @param {string} partnerEmail
 * @param {string} token
 * @returns {Promise<{ message: string, partner: string }>}
 */
export const removePeopleConnection = (partnerEmail, token) =>
  apiFetch(
    `/people/connections/${encodeURIComponent(partnerEmail)}`,
    { method: 'DELETE' },
    token
  );
