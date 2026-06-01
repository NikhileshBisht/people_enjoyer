import React from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeftRight, ChevronRight, LogOut, UserSearch } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './MacnikHubPage.css';

function MacnikLogo() {
  return (
    <div className="macnik-mark" aria-hidden="true">
      M
    </div>
  );
}

function MacnikHubPage() {
  const navigate = useNavigate();
  const { user, authLoading, logout } = useAuth();

  if (authLoading) {
    return <div className="macnik-loading">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="macnik-dashboard">
      <div className="macnik-dashboard-bg" aria-hidden="true" />

      <header className="macnik-dashboard-header">
        <div className="macnik-brand-row">
          <MacnikLogo />
          <span className="macnik-brand-text">Macnik</span>
        </div>
        <div  style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        
        <h3>{user.email}</h3>
            <button type="button" className="macnik-logout-btn" onClick={handleLogout}>
              <LogOut size={16} />
              Logout
            </button>
        
        </div>
      </header>

      <section className="macnik-welcome">
      <p className="macnik-welcome-label">Welcome back,</p>
      </section>

      <div className="macnik-dashboard-cards">
        <button
          type="button"
          className="macnik-dashboard-card macnik-dashboard-card-currency"
          onClick={() => navigate('/currency-exchange')}
        >
          <div className="macnik-dashboard-card-icon currency">
            <ArrowLeftRight size={26} />
          </div>
          <div className="macnik-dashboard-card-body">
            <h2>Currency Exchange</h2>
            <p>Find people nearby who want the opposite currency swap and chat with them.</p>
          </div>
          <ChevronRight size={22} className="macnik-dashboard-chevron" />
        </button>

        <button
          type="button"
          className="macnik-dashboard-card macnik-dashboard-card-people"
          onClick={() => navigate('/people-finder')}
        >
          <div className="macnik-dashboard-card-icon people">
            <UserSearch size={26} />
          </div>
          <div className="macnik-dashboard-card-body">
            <h2>People Finder</h2>
            <p>See who is live around you within your chosen range and start a conversation.</p>
          </div>
          <ChevronRight size={22} className="macnik-dashboard-chevron people-chevron" />
        </button>
      </div>
    </div>
  );
}

export default MacnikHubPage;
