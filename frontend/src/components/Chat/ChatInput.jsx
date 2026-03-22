import React, { useState, useEffect, useRef } from 'react';
import TextareaAutosize from 'react-textarea-autosize';
import { Send, Square, Brain } from 'lucide-react';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

const ChatInput = ({ input, setInput, onSubmit, isLoading, onStop, contextTurns = 0 }) => {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const debounceRef = useRef(null);
  const wrapperRef = useRef(null);

  useEffect(() => {
    if (!input.trim() || input.trim().length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetch(`${API_BASE}/api/suggest?q=${encodeURIComponent(input.trim())}`)
        .then(r => r.json())
        .then(d => {
          setSuggestions(d.suggestions || []);
          setShowSuggestions((d.suggestions || []).length > 0);
          setSelectedIdx(-1);
        })
        .catch(() => {});
    }, 200);
    return () => clearTimeout(debounceRef.current);
  }, [input]);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const pickSuggestion = (text) => {
    setInput(text);
    setShowSuggestions(false);
    setSuggestions([]);
  };

  const handleKeyDown = (e) => {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIdx(prev => (prev + 1) % suggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIdx(prev => (prev <= 0 ? suggestions.length - 1 : prev - 1));
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey && selectedIdx >= 0)) {
        e.preventDefault();
        pickSuggestion(suggestions[selectedIdx >= 0 ? selectedIdx : 0]);
        return;
      }
      if (e.key === 'Escape') {
        setShowSuggestions(false);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      setShowSuggestions(false);
      onSubmit(e);
    }
  };

  return (
    <form className="input-area" onSubmit={(e) => { setShowSuggestions(false); onSubmit(e); }}>
      {contextTurns > 0 && (
        <div className="context-indicator">
          <Brain size={12} /> Using {contextTurns} previous turn{contextTurns > 1 ? 's' : ''} as context
        </div>
      )}
      <div className="input-wrapper" ref={wrapperRef}>
        {showSuggestions && suggestions.length > 0 && (
          <div className="suggest-dropdown">
            {suggestions.map((s, i) => (
              <div
                key={i}
                className={`suggest-item ${i === selectedIdx ? 'suggest-item-active' : ''}`}
                onMouseDown={() => pickSuggestion(s)}
                onMouseEnter={() => setSelectedIdx(i)}
              >
                {s}
              </div>
            ))}
          </div>
        )}
        <TextareaAutosize
          className="chat-input"
          placeholder="Ask about GitLab's handbook or direction..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          disabled={isLoading}
          minRows={1}
          maxRows={6}
          style={{ resize: 'none' }}
        />
        {isLoading ? (
          <button 
            type="button" 
            className="send-btn stop-btn" 
            onClick={onStop}
            title="Stop generating"
            aria-label="Stop generating"
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button 
            type="submit" 
            className="send-btn" 
            disabled={!input.trim()}
            title="Send query"
            aria-label="Send query"
          >
            <Send size={18} />
          </button>
        )}
      </div>
    </form>
  );
};

export default ChatInput;
