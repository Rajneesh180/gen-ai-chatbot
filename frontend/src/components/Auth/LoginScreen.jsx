import React, { useState } from 'react';
import { Gitlab, ArrowRight } from 'lucide-react';

const LoginScreen = ({ onLogin }) => {
  const [name, setName] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    onLogin(trimmed);
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-logo">
          <Gitlab size={48} color="#fc6d26" />
        </div>
        <h1 className="login-title">GitLab Knowledge AI</h1>
        <p className="login-subtitle">
          Your intelligent assistant for GitLab's handbook, values, and engineering practices.
        </p>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-label" htmlFor="username">Enter your name to get started</label>
          <div className="login-input-wrapper">
            <input
              id="username"
              type="text"
              className="login-input"
              placeholder="e.g. Rajneesh"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              maxLength={50}
            />
            <button type="submit" className="login-btn" disabled={!name.trim()}>
              <ArrowRight size={20} />
            </button>
          </div>
        </form>

        <p className="login-note">
          Your chat history will be saved locally under your name.
        </p>
      </div>
    </div>
  );
};

export default LoginScreen;
