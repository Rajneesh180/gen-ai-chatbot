import React from 'react';
import TextareaAutosize from 'react-textarea-autosize';
import { Send, Square } from 'lucide-react';

const ChatInput = ({ input, setInput, onSubmit, isLoading, onStop }) => {
  const handleKeyDown = (e) => {
    // Submit on Enter (unless Shift is held for new line)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e);
    }
  };

  return (
    <form className="input-area" onSubmit={onSubmit}>
      <div className="input-wrapper">
        <TextareaAutosize
          className="chat-input"
          placeholder="Ask about GitLab's handbook or direction..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
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
