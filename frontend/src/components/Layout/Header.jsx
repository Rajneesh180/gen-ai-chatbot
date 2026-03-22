import React from 'react';
import { Gitlab, Download, Trash2 } from 'lucide-react';

const Header = ({ onExport, onClear, hasMessages }) => {
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
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="export-btn" onClick={onClear} title="Clear Chat">
            <Trash2 size={18} />
            <span>Clear</span>
          </button>
          <button className="export-btn" onClick={onExport} title="Export Chat">
            <Download size={18} />
            <span>Export</span>
          </button>
        </div>
      )}
    </header>
  );
};

export default Header;
