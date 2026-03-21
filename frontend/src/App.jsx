import React, { useState, useRef, useEffect } from 'react';
import { Gitlab } from 'lucide-react';
import Header from './components/Layout/Header';
import ChatInput from './components/Chat/ChatInput';
import MessageBubble from './components/Chat/MessageBubble';
import './index.css';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

const TOPIC_STARTERS = [
  "What are GitLab's core values?",
  "How does remote work function at GitLab?",
  "What is the product development flow?",
  "How are performance reviews conducted?",
  "What are the security practices for code review?",
  "Explain the significance of async communication."
];

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

  const handleExport = () => {
    if (messages.length === 0) return;
    
    let mdContent = "# GitLab Knowledge AI Chat Export\n\n";
    messages.forEach(msg => {
      const roleName = msg.role === 'user' ? '👤 You' : '🦊 GitLab AI';
      mdContent += `### ${roleName}\n${msg.content}\n\n`;
      
      if (msg.sources && msg.sources.length > 0) {
        mdContent += "**Sources:**\n";
        msg.sources.forEach((s) => {
          mdContent += `- [${s.title}](${s.url})\n`;
        });
        mdContent += "\n";
      }
      mdContent += "---\n\n";
    });

    const blob = new Blob([mdContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gitlab-chat-export-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFeedback = async (messageIndex, rating) => {
    const msg = messages[messageIndex];
    if (msg.feedbackGiven) return;

    setMessages(prev => {
      const updated = [...prev];
      updated[messageIndex] = { ...updated[messageIndex], feedbackGiven: rating };
      return updated;
    });

    let query = "";
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        query = messages[i].content;
        break;
      }
    }

    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          answer: msg.content,
          rating: rating
        })
      });
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

  const handleSubmit = async (e, forcedInput = null) => {
    if (e) e.preventDefault();
    const queryToUse = forcedInput || input;
    if (!queryToUse.trim() || isLoading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: queryToUse }]);
    setIsLoading(true);

    try {
      const history = [];
      for (let i = 0; i < messages.length; i += 2) {
        if (messages[i] && messages[i+1]) {
           history.push([messages[i].content, messages[i+1].content]);
        }
      }

      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryToUse, history: history }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Network response was not ok');
      }

      setMessages(prev => [...prev, { 
        role: 'bot', 
        content: '', 
        sources: [], 
        retrievalDetails: [], 
        metadata: null, 
        suggestions: [],
        feedbackGiven: null,
        showDetails: false
      }]);
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let buffer = '';
      let accumulatedContent = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';
          
          for (const eventStr of parts) {
            if (eventStr.startsWith('data: ')) {
              try {
                const dataStr = eventStr.slice(6);
                if (dataStr === '{"type": "done"}') {
                  done = true;
                  continue;
                }

                const data = JSON.parse(dataStr);
                
                setMessages(prev => {
                  const updated = [...prev];
                  const lastMsg = { ...updated[updated.length - 1] };
                  
                  if (data.type === 'sources') {
                    lastMsg.sources = data.sources;
                  } else if (data.type === 'retrieval_details') {
                    lastMsg.retrievalDetails = data.details;
                  } else if (data.type === 'token') {
                     accumulatedContent += data.text;
                     lastMsg.content = accumulatedContent;
                  } else if (data.type === 'content') {
                     accumulatedContent = data.text;
                     lastMsg.content = accumulatedContent;
                  } else if (data.type === 'metadata') {
                     lastMsg.metadata = data.metadata;
                  } else if (data.type === 'suggestions') {
                     lastMsg.suggestions = data.suggestions;
                  }
                  
                  updated[updated.length - 1] = lastMsg;
                  return updated;
                });
              } catch (e) { }
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      let errMsg = 'Sorry, an error occurred.';
      if (error.message.includes('No such file') || error.message.includes('Database Error')) {
         errMsg = '⚠️ **Database Missing**: The ingestion pipeline has not finished running.';
      }
      setMessages(prev => [...prev, { role: 'bot', content: errMsg, sources: [] }]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleDetails = (index) => {
    setMessages(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], showDetails: !updated[index].showDetails };
      return updated;
    });
  };

  return (
    <div className="app-container">
      <div className="glass-panel main-glass">
        <Header onExport={handleExport} hasMessages={messages.length > 0} />

        <div className="chat-container">
          {messages.length === 0 && (
            <div className="empty-state fade-in-up">
              <div className="empty-icon-wrapper">
                <Gitlab size={48} color="#fc6d26" />
              </div>
              <h2>Welcome to GitLab Knowledge AI</h2>
              <p>Ask me anything about GitLab's core values, remote work, engineering practices, or product development flows.</p>
              
              <div className="topic-starters">
                {TOPIC_STARTERS.map((topic, idx) => (
                  <button 
                    key={idx} 
                    className="topic-chip"
                    onClick={() => handleSubmit(null, topic)}
                  >
                    {topic}
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {messages.map((msg, idx) => {
            const isLatestBotMsg = msg.role === 'bot' && idx === messages.length - 1;
            return (
              <MessageBubble 
                key={idx} 
                msg={msg} 
                idx={idx} 
                isLatestBotMsg={isLatestBotMsg} 
                isLoading={isLoading} 
                onToggleDetails={toggleDetails} 
                onFeedback={handleFeedback} 
                onSuggestionClick={(sug) => handleSubmit(null, sug)}
              />
            );
          })}
          
          <div ref={messagesEndRef} />
        </div>

        <ChatInput 
          input={input} 
          setInput={setInput} 
          onSubmit={handleSubmit} 
          isLoading={isLoading} 
        />
      </div>
    </div>
  );
}

export default App;
