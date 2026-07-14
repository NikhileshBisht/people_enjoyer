import React, { useState } from 'react';
import Cropper from 'react-easy-crop';
import { saveEnjoyerProfile } from '../api/enjoyer';
import './ProfilePopup.css';

const PROFILE_ID_KEY = 'enjoyer_profile_id';

function ProfilePopup({ open, onClose, token }) {
  const [formData, setFormData] = useState({
    name: '',
    age: '',
    bio: '',
    pictures: [null, null, null, null],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [showCropModal, setShowCropModal] = useState(false);
  const [editingImage, setEditingImage] = useState(null);

  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleImageUpload = (e, index) => {
    const file = e.target.files[0];
    if (!file) return;

    const updatedPictures = [...formData.pictures];
    updatedPictures[index] = file;

    setFormData({
      ...formData,
      pictures: updatedPictures,
    });
  };

  const handleRemoveImage = (index) => {
    const updatedPictures = [...formData.pictures];
    updatedPictures[index] = null;

    setFormData({
      ...formData,
      pictures: updatedPictures,
    });
  };

  const handleOpenEditor = (index) => {
    setEditingImage(index);
    setShowCropModal(true);
  };

  const handleSave = async () => {
    setError('');
    const uploadedImages = formData.pictures.filter(Boolean);

    if (!formData.name.trim() || !formData.age || !formData.bio.trim()) {
      setError('Please complete name, age, and bio.');
      return;
    }

    if (uploadedImages.length !== 4) {
      setError('Please upload exactly 4 pictures.');
      return;
    }

    const profileId = Number(localStorage.getItem(PROFILE_ID_KEY) || 0);

    setSaving(true);
    try {
      const result = await saveEnjoyerProfile({
        name: formData.name.trim(),
        age: Number(formData.age),
        bio: formData.bio.trim(),
        photos: uploadedImages,
        profileId,
        token,
      });

      if (result?.profile?.id) {
        localStorage.setItem(PROFILE_ID_KEY, String(result.profile.id));
      }

      alert('Profile saved successfully.');
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className={`profile-popup-overlay ${open ? 'show' : ''}`}>
        <div className="profile-popup">
          <button type="button" className="close-popup-btn" onClick={onClose}>
            ✕
          </button>

          <h2>Create Profile</h2>

          <div className="profile-form">
            <input
              type="text"
              name="name"
              placeholder="Enter Name"
              value={formData.name}
              onChange={handleChange}
              disabled={saving}
            />

            <input
              type="number"
              name="age"
              placeholder="Enter Age"
              value={formData.age}
              onChange={handleChange}
              disabled={saving}
            />

            <textarea
              name="bio"
              rows="5"
              placeholder="Write Bio"
              value={formData.bio}
              onChange={handleChange}
              disabled={saving}
            />

            <div className="image-grid">
              {formData.pictures.map((picture, index) => (
                <div key={index} className="image-upload-card">
                  {picture ? (
                    <>
                      <img
                        src={URL.createObjectURL(picture)}
                        alt="preview"
                        className="preview-image"
                        onClick={() => handleOpenEditor(index)}
                      />

                      <div className="image-overlay">
                        <button
                          type="button"
                          className="edit-image-btn"
                          onClick={() => handleOpenEditor(index)}
                        >
                          Edit
                        </button>

                        <button
                          type="button"
                          className="remove-image-btn"
                          onClick={() => handleRemoveImage(index)}
                        >
                          ✕
                        </button>
                      </div>
                    </>
                  ) : (
                    <label className="upload-placeholder">
                      <span>+</span>
                      <p>Add Photo</p>

                      <input
                        type="file"
                        accept="image/*"
                        hidden
                        onChange={(e) => handleImageUpload(e, index)}
                      />
                    </label>
                  )}
                </div>
              ))}
            </div>

            {error && <div className="profile-error">{error}</div>}

            <button
              type="button"
              className="save-profile-btn"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </div>
      </div>

      {showCropModal && editingImage !== null && (
        <div className="crop-modal-overlay">
          <div className="crop-modal">
            <button
              type="button"
              className="close-crop-btn"
              onClick={() => setShowCropModal(false)}
            >
              ✕
            </button>

            <div className="crop-header">
              <h3>Edit Photo</h3>
              <p>Drag and zoom your image</p>
            </div>

            <div className="crop-container">
              <Cropper
                image={URL.createObjectURL(formData.pictures[editingImage])}
                crop={crop}
                zoom={zoom}
                aspect={3 / 4}
                onCropChange={setCrop}
                onZoomChange={setZoom}
              />
            </div>

            <div className="crop-controls">
              <label>Zoom</label>

              <input
                type="range"
                min={1}
                max={3}
                step={0.1}
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
              />

              <button
                type="button"
                className="save-crop-btn"
                onClick={() => setShowCropModal(false)}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default ProfilePopup;
