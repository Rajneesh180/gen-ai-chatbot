import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Gitlab, User, Send } from 'lucide-react';
import './index.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userQuery = input.trim();
    setInput('');
    
    setMessages(prev => [...prev, { role: 'user', content: userQuery }]);
    setIsLoading(true);

    try {
      const history = [];
      for (let i = 0; i < messages.length; i += 2) {
        if (messages[i] && messages[i+1]) {
           history.push([messages[i].content, messages[i+1].content]);
        }
      }

      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userQuery, history: history }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Network response was not ok');
      }

      setMessages(prev => [...prev, { role: 'bot', content: '', sources: [] }]);
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          const events = chunk.split('\n\n');
          
          events.forEach(eventStr => {
            if (eventStr.startsWith('data: ')) {
              try {
                const data = JSON.parse(eventStr.slice(6));
                
                if (data.type === 'sources') {
                  setMessages(prev => {
                    const updated = [...prev];
                    updated[updated.length - 1].sources = data.sources;
                    return updated;
                  });
                } else if (data.type === 'content') {
                  setMessages(prev => {
                    const updated = [...prev];
                    updated[updated.length - 1].content += data.text;
                    return updated;
                  });
                } else if (data.type === 'done') {
                  done = true;
                }
              } catch (e) { }
            }
          });
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      let errMsg = 'Sorry, an error occurred.';
      if (error.message.includes('No such file') || error.message.includes('Database Error')) {
         errMsg = '⚠️ **Database Missing**: The ingestion pipeline has not finished running. Please run `python -m backend.ingestion.run_ingest --from embed` to generate the AI memory context!';
      }
      setMessages(prev => [...prev, { role: 'bot', content: errMsg, sources: [] }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <div className="glass-panel">
        <header className="header">
          <div className="header-icon" style={{ display: 'flex', alignItems: 'center' }}>
            <Gitlab size={38} color="#fc6d26" strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="header-title">GitLab Knowledge AI</h1>
            <p className="header-subtitle">Intelligent answers grounded in GitLab's Handbook & Direction pages</p>
          </div>
        </header>

        <div className="chat-container">
          {messages.length === 0 && (
            <div className="message bot" style={{ display: 'flex', gap: '12px' }}>
              <div style={{ marginTop: '2px' }}><Gitlab size={24} color="#fc6d26" /></div>
              <div>
                <p>Hi! I'm the **GitLab Knowledge Assistant**. Ask me anything about GitLab's core values, remote work, or product development flows.</p>
              </div>
            </div>
          )}
          
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`} style={{ display: 'flex', gap: '12px', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
              {msg.role === 'bot' && <div style={{ marginTop: '2px', minWidth: '24px' }}><Gitlab size={24} color="#fc6d26" /></div>}
              
              <div style={{ maxWidth: '100%' }}>
                <ReactMarkdown>{msg.content}</ReactMarkdown>
                
                {msg.sources && msg.sources.length > 0 && (
                  <div className="sources-container">
                    <div className="sources-title">📚 Sources</div>
                    <div className="source-badges">
                      {msg.sources.map((src, sIdx) => (
                        <a key={sIdx} href={src.url} target="_blank" rel="noreferrer" className="source-badge">
                          {src.title || new URL(src.url).pathname.split('/').pop() || 'Handbook Page'}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              
              {msg.role === 'user' && <div style={{ marginTop: '2px', minWidth: '24px', opacity: 0.8 }}><User size={24} color="#e0e6ed" /></div>}
            </div>
          ))}
          
          {isLoading && (
            <div className="message bot" style={{ display: 'flex', gap: '12px' }}>
              <div style={{ marginTop: '2px' }}><Gitlab size={24} color="#fc6d26" /></div>
              <div className="typing-indicator" style={{ padding: '4px 0' }}>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="input-container" onSubmit={handleSubmit}>
          <input
            type="text"
            className="input-field"
            placeholder="Ask about GitLab's handbook or direction..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
          />
          <button type="submit" className="send-btn" disabled={!input.trim() || isLoading}>
            <Send size={18} style={{ marginRight: '8px' }} />
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
