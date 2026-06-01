import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import './App.css';
import { AuthProvider } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import MacnikHubPage from './pages/MacnikHubPage';
import CurrencyExchangePage from './pages/CurrencyExchangePage';
import PeopleFinderPage from './pages/PeopleFinderPage';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/macnik" element={<MacnikHubPage />} />
          <Route path="/currency-exchange" element={<CurrencyExchangePage />} />
          <Route path="/people-finder" element={<PeopleFinderPage />} />
          <Route path="/CurrencyExchange" element={<Navigate to="/currency-exchange" replace />} />
          <Route path="/map" element={<Navigate to="/macnik" replace />} />
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
