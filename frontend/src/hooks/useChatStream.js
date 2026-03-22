import { useState, useRef } from 'react';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

export const useChatStream = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Abort controller reference to cancel streams
  const abortControllerRef = useRef(null);

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
        body: JSON.stringify({ query, answer: msg.content, rating })
      });
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

  const toggleDetails = (index) => {
    setMessages(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], showDetails: !updated[index].showDetails };
      return updated;
    });
  };

  const stopGenerating = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e, forcedInput = null) => {
    if (e && e.preventDefault) e.preventDefault();
    const queryToUse = forcedInput || input;
    if (!queryToUse.trim() || isLoading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: queryToUse }]);
    setIsLoading(true);

    // Set up new abort controller for this request
    abortControllerRef.current = new AbortController();

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
        body: JSON.stringify({ query: queryToUse, history }),
        signal: abortControllerRef.current.signal
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
      if (error.name === 'AbortError') {
        console.log('Stream aborted by user');
      } else {
        console.error('Chat error:', error);
        let errMsg = 'Sorry, an error occurred.';
        if (error.message.includes('No such file') || error.message.includes('Database Error')) {
           errMsg = '⚠️ **Database Missing**: The ingestion pipeline has not finished running.';
        }
        setMessages(prev => [...prev, { role: 'bot', content: errMsg, sources: [] }]);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  return {
    messages,
    input,
    setInput,
    isLoading,
    handleSubmit,
    handleFeedback,
    toggleDetails,
    stopGenerating
  };
};
