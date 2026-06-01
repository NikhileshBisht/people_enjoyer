import React from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import LocationPicker from '../components/LocationPicker';
import { useAuth } from '../context/AuthContext';

function MapPage() {
  const navigate = useNavigate();
  const { token, user, authLoading, logout } = useAuth();

  if (authLoading) {
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
      <div className="auth-topbar">
        <span className="auth-user">Logged in as {user.email}</span>
        <button type="button" className="logout-btn" onClick={handleLogout}>
          Logout
        </button>
      </div>
      <LocationPicker token={token} currentUser={user} onLogout={handleLogout} />
    </div>
  );
}

export default MapPage;
