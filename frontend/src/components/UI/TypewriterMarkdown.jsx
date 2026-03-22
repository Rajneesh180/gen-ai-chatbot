import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';

const TypewriterMarkdown = ({ content, animate = true, minDelay = 5, maxDelay = 15 }) => {
  const [displayedContent, setDisplayedContent] = useState('');
  const [isTyping, setIsTyping] = useState(animate);
  const currentIndexRef = useRef(0);

  useEffect(() => {
    // If we're not animating, show the full content immediately
    if (!animate) {
      setDisplayedContent(content);
      setIsTyping(false);
      return;
    }

    // If we are animating but the content is empty, just reset
    if (!content) {
      setDisplayedContent('');
      currentIndexRef.current = 0;
      setIsTyping(true);
      return;
    }

    // Reset if content changed entirely while we were typing
    if (currentIndexRef.current > content.length) {
      setDisplayedContent('');
      currentIndexRef.current = 0;
    }

    let timeoutId;
    
    const typeNextChar = () => {
      if (currentIndexRef.current < content.length) {
        // Process slightly more characters at once for faster typing and better markdown handling
        const chunkSize = 3;
        currentIndexRef.current = Math.min(currentIndexRef.current + chunkSize, content.length);
        
        setDisplayedContent(content.substring(0, currentIndexRef.current));
        
        // Randomize typing speed for a more human feel
        const delay = Math.floor(Math.random() * (maxDelay - minDelay + 1)) + minDelay;
        timeoutId = setTimeout(typeNextChar, delay);
      } else {
        setIsTyping(false);
      }
    };

    if (isTyping) {
      timeoutId = setTimeout(typeNextChar, minDelay);
    }

    return () => clearTimeout(timeoutId);
  }, [content, animate, minDelay, maxDelay, isTyping]);

  return (
    <div className={`markdown-body ${isTyping ? 'typing-active' : ''}`}>
      <ReactMarkdown>{displayedContent}</ReactMarkdown>
    </div>
  );
};

export default TypewriterMarkdown;
