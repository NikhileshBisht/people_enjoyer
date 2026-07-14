/**
 * api/chat.js
 * Chat REST endpoints (conversations list & message history).
 * Real-time messaging is handled via WebSocket — see api/socket.js.
 *
 * `module` is either 'people' or 'currency', matching the backend route.
 */

import { apiFetch } from './config';

/**
 * Fetch all conversations for the authenticated user in a given module.
 * @param {'people'|'currency'} module
 * @param {string} token
 * @returns {Promise<{ conversations: object[] }>}
 */
export const getConversations = (module, token) =>
  apiFetch(`/chat/${module}/conversations`, {}, token);

/**
 * Fetch message history between the viewer and a partner.
 * @param {'people'|'currency'} module
 * @param {string} partnerEmail
 * @param {string} token
 * @returns {Promise<{ partner: object, messages: object[] }>}
 */
export const getMessages = (module, partnerEmail, token) =>
  apiFetch(
    `/chat/${module}/messages/${encodeURIComponent(partnerEmail)}`,
    {},
    token
  );
