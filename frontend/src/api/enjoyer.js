/**
 * api/enjoyer.js
 * Enjoyer profile endpoints.
 *
 * Uses multipart/form-data (no JSON) because photos are binary files.
 * apiFetch() is NOT used here since it always sets Content-Type: application/json.
 */

import { API_BASE_URL } from './config';

/**
 * Create or update an enjoyer profile.
 *
 * @param {object} params
 * @param {string}   params.name
 * @param {number}   params.age
 * @param {string}   [params.bio]
 * @param {File[]}   params.photos   - exactly 4 File objects
 * @param {number}   [params.profileId=0]  - 0 = create new
 * @param {string}   [params.token]  - JWT (optional, add if you secure the endpoint later)
 * @returns {Promise<{ profile: object }>}
 */
export async function saveEnjoyerProfile({ name, age, bio = '', photos, profileId = 0, token = null }) {
  const form = new FormData();
  form.append('name', name);
  form.append('age', String(age));
  form.append('bio', bio);
  form.append('profile_id', String(profileId));

  photos.forEach((file) => {
    form.append('photos', file);
  });

  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}/enjoyer/profile`, {
    method: 'POST',
    headers,
    body: form,          // let the browser set multipart boundary automatically
  });

  const data = await response.json();

  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
        ? detail.map((e) => e.msg).join(', ')
        : 'Failed to save profile.';
    throw new Error(message);
  }

  return data;
}

/**
 * Fetch an enjoyer profile by its DB id.
 * @param {number} profileId
 * @returns {Promise<{ profile: object }>}
 */
export async function getEnjoyerProfile(profileId) {
  const response = await fetch(`${API_BASE_URL}/enjoyer/profile/${profileId}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.detail || 'Profile not found.');
  }
  return data;
}
