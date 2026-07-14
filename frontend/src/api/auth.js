/**
 * api/auth.js
 * Authentication endpoints — OTP-based register & login.
 */

import { apiFetch } from './config';

/**
 * Request a registration OTP to the given email.
 * @param {string} email
 * @returns {Promise<{ message: string }>}
 */
export const requestRegisterOtp = (email) =>
  apiFetch('/auth/register/request-otp', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });

/**
 * Verify the registration OTP.
 * @param {string} email
 * @param {string} otp
 * @returns {Promise<{ access_token: string }>}
 */
export const verifyRegisterOtp = (email, otp) =>
  apiFetch('/auth/register/verify-otp', {
    method: 'POST',
    body: JSON.stringify({ email, otp }),
  });

/**
 * Request a login OTP to the given email.
 * @param {string} email
 * @returns {Promise<{ message: string }>}
 */
export const requestLoginOtp = (email) =>
  apiFetch('/auth/login/request-otp', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });

/**
 * Verify the login OTP.
 * @param {string} email
 * @param {string} otp
 * @returns {Promise<{ access_token: string }>}
 */
export const verifyLoginOtp = (email, otp) =>
  apiFetch('/auth/login/verify-otp', {
    method: 'POST',
    body: JSON.stringify({ email, otp }),
  });
