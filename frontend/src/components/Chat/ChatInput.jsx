import React from 'react';
import { Send } from 'lucide-react';

const ChatInput = ({ input, setInput, onSubmit, isLoading }) => {
  return (
    <form className="input-area" onSubmit={onSubmit}>
      <div className="input-wrapper">
        <input
          type="text"
          className="chat-input"
          placeholder="Ask about GitLab's handbook or direction..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading}
        />
        <button type="submit" className="send-btn" disabled={!input.trim() || isLoading}>
          <Send size={18} />
        </button>
      </div>
    </form>
  );
};

export default ChatInput;
