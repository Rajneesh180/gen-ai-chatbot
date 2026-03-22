import React, { useRef, useEffect } from 'react';
import { Gitlab } from 'lucide-react';
import Header from './components/Layout/Header';
import ChatInput from './components/Chat/ChatInput';
import MessageBubble from './components/Chat/MessageBubble';
import { useChatStream } from './hooks/useChatStream';
import './index.css';

const TOPIC_STARTERS = [
  "What are GitLab's core values?",
  "How does remote work function at GitLab?",
  "What is the product development flow?",
  "How are performance reviews conducted?",
  "What are the security practices for code review?",
  "Explain the significance of async communication."
];

function App() {
  const {
    messages,
    input,
    setInput,
    isLoading,
    handleSubmit,
    handleFeedback,
    toggleDetails,
    stopGenerating,
    clearChat
  } = useChatStream();

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

  return (
    <div className="app-container">
      <div className="glass-panel main-glass">
        <Header onExport={handleExport} onClear={clearChat} hasMessages={messages.length > 0} />

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
          onStop={stopGenerating}
        />
      </div>
    </div>
  );
}

export default App;
