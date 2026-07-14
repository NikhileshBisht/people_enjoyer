import React, { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import Cookies from 'js-cookie';

import LocationPicker from '../components/LocationPicker';
import ProfilePopup from '../components/ProfilePopup';
import { useAuth } from '../context/AuthContext';

function FeatureMapPage({ mode, title }) {
  const navigate = useNavigate();
  const { token, user, authLoading, logout } = useAuth();

  const [showPopup, setShowPopup] = useState(false);
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);

  useEffect(() => {
    const fetchProfile = async () => {
      if (title === 'Currency Exchange') {
        setProfileLoading(false);
        return;
      }
  
      const profileId = Cookies.get('enjoyer_profile_id');
  
      if (!profileId) {
        setShowPopup(true);
        setProfileLoading(false);
        return;
      }
  
      try {
        const response = await fetch(
          `http://localhost:8000/enjoyer/profile/${profileId}`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          }
        );
  
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
  
        const data = await response.json();
  
        setProfile(data.profile);
      } catch (error) {
        console.error('Failed to fetch profile:', error);
        setShowPopup(true);
      } finally {
        setProfileLoading(false);
      }
    };
  
    if (token) {
      fetchProfile();
    }
  }, [title, token]);

  if (authLoading || profileLoading) {
    return <div className="auth-loading">Loading...</div>;
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="App">
      <div className="auth-topbar feature-topbar">
        <button
          type="button"
          className="back-macnik-btn"
          onClick={() => navigate('/macnik')}
        >
          ← BACK
        </button>

        <span className="feature-title">{title}</span>

        <div className="topbar-right-peoplefinder">
          <span className="auth-user">{user.email}</span>

          {title !== 'Currency Exchange' && (
            <button
              className="profile-open-btn"
              onClick={() => setShowPopup(true)}
            >
              {profile ? 'Edit Profile' : 'Complete Profile'}
            </button>
          )}

          <button
            type="button"
            className="logout-btn"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </div>

      <LocationPicker
        token={token}
        mode={mode}
        embedded
        onBack={() => navigate('/macnik')}
      />

      <ProfilePopup
        open={showPopup}
        onClose={() => setShowPopup(false)}
        token={token}
        profile={profile}
      />
    </div>
  );
}

export default FeatureMapPage;