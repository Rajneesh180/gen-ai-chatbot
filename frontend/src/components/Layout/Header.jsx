import React from 'react';
import { Gitlab, Download } from 'lucide-react';

const Header = ({ onExport, hasMessages }) => {
  return (
    <header className="header premium-header">
      <div className="header-brand">
        <div className="icon-wrapper">
          <Gitlab size={32} color="#fc6d26" strokeWidth={2} />
        </div>
        <div>
          <h1 className="header-title">GitLab Knowledge AI</h1>
          <p className="header-subtitle">Intelligent answers from Handbook & Direction</p>
        </div>
      </div>
      {hasMessages && (
        <button className="export-btn" onClick={onExport} title="Export Chat">
          <Download size={18} />
          <span>Export</span>
        </button>
      )}
    </header>
  );
};

export default Header;
