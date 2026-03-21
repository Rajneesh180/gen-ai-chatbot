import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Gitlab, User, ThumbsUp, ThumbsDown, ShieldCheck, ShieldAlert, Info } from 'lucide-react';
import TypewriterMarkdown from '../UI/TypewriterMarkdown';
import RetrievalPanel from './RetrievalPanel';

const MessageBubble = ({ 
  msg, 
  idx, 
  isLatestBotMsg, 
  isLoading, 
  onToggleDetails, 
  onFeedback, 
  onSuggestionClick 
}) => {
  const renderConfidenceBadge = (metadata) => {
    if (!metadata || metadata.confidence < 0) return null;
    
    let colorClass, icon, label;
    if (metadata.confidence >= 80) {
      colorClass = 'confidence-high';
      icon = <ShieldCheck size={14} />;
      label = 'High Confidence';
    } else if (metadata.confidence >= 50) {
      colorClass = 'confidence-med';
      icon = <Info size={14} />;
      label = 'Medium Confidence';
    } else {
      colorClass = 'confidence-low';
      icon = <ShieldAlert size={14} />;
      label = 'Low Confidence';
    }

    return (
      <div className={`meta-badge ${colorClass}`} title={`Score: ${metadata.confidence}/100 - Type: ${metadata.answer_type}`}>
        {icon} <span>{label}</span>
        {metadata.answer_type === 'inferential' && <span className="meta-sub"> (Inferential)</span>}
      </div>
    );
  };

  return (
    <div className={`message-wrapper ${msg.role} fade-in-up`}>
      <div className={`avatar ${msg.role}`}>
        {msg.role === 'bot' ? <Gitlab size={20} color="#fff" /> : <User size={20} color="#fff" />}
      </div>
      
      <div className="message-content">
        {msg.role === 'bot' && msg.metadata && (
          <div className="message-header">
            {renderConfidenceBadge(msg.metadata)}
          </div>
        )}
        
        {msg.role === 'bot' && msg.metadata?.guardrail_note && (
          <div className="guardrail-note">
            <Info size={14} /> {msg.metadata.guardrail_note}
          </div>
        )}

        {msg.role === 'bot' && isLatestBotMsg && isLoading && !msg.content ? (
          <div className="typing-indicator" style={{ minHeight: '24px', paddingLeft: '4px' }}>
            <div className="jumping-dot"></div>
            <div className="jumping-dot" style={{ animationDelay: '0.2s' }}></div>
            <div className="jumping-dot" style={{ animationDelay: '0.4s' }}></div>
          </div>
        ) : msg.role === 'bot' ? (
          <TypewriterMarkdown 
            content={msg.content} 
            animate={isLatestBotMsg} 
            minDelay={15} 
            maxDelay={45} 
          />
        ) : (
          <div className="markdown-body">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        )}

        {msg.role === 'bot' && msg.sources && msg.sources.length > 0 && (
          <div className="sources-container">
            <div className="sources-title">
              📚 Sources Used
            </div>
            <div className="source-badges">
              {msg.sources.map((src, sIdx) => (
                <a key={sIdx} href={src.url} target="_blank" rel="noreferrer" className="source-badge">
                  {src.title || 'Handbook Page'}
                </a>
              ))}
            </div>
            
            <RetrievalPanel 
              details={msg.retrievalDetails} 
              isExpanded={msg.showDetails} 
              onToggle={() => onToggleDetails(idx)} 
            />
          </div>
        )}

        {msg.role === 'bot' && !isLoading && (
          <div className="message-footer">
            <div className="suggestions-container">
              {msg.suggestions && msg.suggestions.map((sug, sIdx) => (
                <button 
                  key={sIdx} 
                  className="suggestion-chip"
                  onClick={() => onSuggestionClick(sug)}
                >
                  {sug}
                </button>
              ))}
            </div>
            
            <div className="feedback-actions">
              <button 
                className={`feedback-btn ${msg.feedbackGiven === 'up' ? 'active' : ''}`}
                title="Good answer"
                onClick={() => onFeedback(idx, 'up')}
                disabled={msg.feedbackGiven !== null}
              >
                <ThumbsUp size={16} />
              </button>
              <button 
                className={`feedback-btn ${msg.feedbackGiven === 'down' ? 'active' : ''}`}
                title="Bad answer"
                onClick={() => onFeedback(idx, 'down')}
                disabled={msg.feedbackGiven !== null}
              >
                <ThumbsDown size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
