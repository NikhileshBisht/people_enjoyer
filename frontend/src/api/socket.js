/**
 * api/socket.js
 * WebSocket factory for the /ws/match endpoint.
 *
 * Usage:
 *   const socket = createMatchSocket(token, handlers);
 *   // later...
 *   socket.close();
 */

import { WS_BASE_URL } from './config';

/**
 * WebSocket message type constants.
 * Mirror the backend's payload `type` field.
 */
export const WS_MSG = {
  // Outbound (client → server)
  SEARCH: 'search',
  SEARCH_PEOPLE: 'search_people',
  SEND_MESSAGE: 'send_message',

  // Inbound (server → client)
  MATCHES: 'matches',
  PEOPLE_MATCHES: 'people_matches',
  ERROR: 'error',
  CONNECTION_REQUEST: 'connection_request',
  CONNECTION_ACCEPTED: 'connection_accepted',
  CONNECTION_REMOVED: 'connection_removed',
  NEW_MESSAGE: 'new_message',
  MESSAGE_SENT: 'message_sent',
};

/**
 * Open a WebSocket connection to /ws/match.
 *
 * @param {string} token - JWT access token
 * @param {object} handlers
 * @param {Function} [handlers.onOpen]
 * @param {Function} [handlers.onClose]
 * @param {Function} [handlers.onError]
 * @param {Function} [handlers.onMessage]  - receives the parsed JSON payload
 * @returns {WebSocket}
 */
export function createMatchSocket(token, handlers = {}) {
  const socket = new WebSocket(
    `${WS_BASE_URL}/ws/match?token=${encodeURIComponent(token)}`
  );

  socket.onopen = () => handlers.onOpen?.();
  socket.onclose = () => handlers.onClose?.();
  socket.onerror = () => handlers.onError?.();
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      handlers.onMessage?.(payload);
    } catch {
      handlers.onError?.(new Error('Invalid WebSocket message.'));
    }
  };

  return socket;
}

/**
 * Send a currency search query over an open socket.
 * @param {WebSocket} socket
 * @param {{ fromCurrency: string, toCurrency: string, lat: number, lng: number }} params
 */
export function sendCurrencySearch(socket, { fromCurrency, toCurrency, lat, lng }) {
  socket.send(
    JSON.stringify({ type: WS_MSG.SEARCH, fromCurrency, toCurrency, lat, lng })
  );
}

/**
 * Send a people search query over an open socket.
 * @param {WebSocket} socket
 * @param {{ lat: number, lng: number, rangeKm: number }} params
 */
export function sendPeopleSearch(socket, { lat, lng, rangeKm }) {
  socket.send(
    JSON.stringify({ type: WS_MSG.SEARCH_PEOPLE, lat, lng, rangeKm })
  );
}

/**
 * Send a chat message over an open socket.
 * @param {WebSocket} socket
 * @param {{ module: string, toEmail: string, text: string }} params
 */
export function sendChatMessage(socket, { module, toEmail, text }) {
  socket.send(
    JSON.stringify({ type: WS_MSG.SEND_MESSAGE, module, toEmail, text })
  );
}
