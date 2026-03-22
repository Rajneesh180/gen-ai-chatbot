import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Gitlab, User, ThumbsUp, ThumbsDown, ShieldCheck, ShieldAlert, Info, BookOpen } from 'lucide-react';
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
        ) : isLatestBotMsg && isLoading ? (
          /* During streaming: render as plain text for speed — avoids O(n²)
             ReactMarkdown re-parsing on every token and prevents partial
             markdown like [Values](url showing as raw text */
          <div className="markdown-body typing-active">
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{msg.content}</div>
          </div>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({node, inline, className, children, ...props}) {
                  const match = /language-(\w+)/.exec(className || '')
                  return !inline && match ? (
                    <SyntaxHighlighter
                      {...props}
                      children={String(children).replace(/\n$/, '')}
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      customStyle={{
                        background: 'rgba(0,0,0,0.5)',
                        padding: '16px',
                        borderRadius: '8px',
                        margin: '12px 0',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                      }}
                    />
                  ) : (
                    <code {...props} className={className}>
                      {children}
                    </code>
                  )
                }
              }}
            >
              {msg.content}
            </ReactMarkdown>
          </div>
        )}

        {msg.role === 'bot' && msg.sources && msg.sources.length > 0 && (
          <div className="sources-container">
            <div className="sources-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BookOpen size={18} className="text-primary" /> Sources Used
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
                aria-label="Thumbs up"
                onClick={() => onFeedback(idx, 'up')}
                disabled={msg.feedbackGiven !== null}
              >
                <ThumbsUp size={16} />
              </button>
              <button 
                className={`feedback-btn ${msg.feedbackGiven === 'down' ? 'active' : ''}`}
                title="Bad answer"
                aria-label="Thumbs down"
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
