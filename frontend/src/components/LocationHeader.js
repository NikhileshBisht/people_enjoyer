import React from 'react';
import { MapPin, ChevronDown } from 'lucide-react';
import './LocationPicker.css';

const LocationHeader = ({ currentAddress, subAddress, onClick }) => {
  return (
    <div className="header-display" onClick={onClick}>
      <div className="header-location-icon">
        <MapPin size={24} fill="currentColor" stroke="white" />
      </div>
      <div className="header-address-text">
        <div className="header-address-main">
          {currentAddress || "Select Location"}
          <ChevronDown size={14} color="#ff3269" />
        </div>
        <div className="header-address-sub">
          {subAddress || "Set your delivery address to see offerings"}
        </div>
      </div>
    </div>
  );
};

export default LocationHeader;
