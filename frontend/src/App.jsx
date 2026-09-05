import React, { useState, useEffect, useRef } from 'react';
import StatusPanel from './components/StatusPanel';
import Message from './components/Message';
import { Send, Terminal } from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesListRef = useRef(null);

  useEffect(() => {
    // Check real auth status on load
    fetch('/auth/status')
      .then(res => res.json())
      .then(data => setIsAuthenticated(data.authenticated))
      .catch(() => setIsAuthenticated(false));
  }, []);

  const scrollToBottom = () => {
    if (messagesListRef.current) {
      messagesListRef.current.scrollTo({
        top: messagesListRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (actionQuery) => {
    const textToSend = (typeof actionQuery === 'string' ? actionQuery : inputValue).trim();
    if (!textToSend) return;
    
    const userMsg = { role: 'user', content: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: textToSend })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        if (response.status === 401) {
          setIsAuthenticated(false);
          throw new Error('Session expired. Please re-authenticate.');
        }
        throw new Error(errorData?.error || 'Failed to send message');
      }
      
      const data = await response.json();
      
      const agentMsg = {
        role: 'agent',
        content: data.response || 'No response from Swiggy.',
        active_server: data.active_server,
        rankings: data.rankings || [],
        tool_calls: data.tool_calls || []
      };
      
      setMessages(prev => [...prev, agentMsg]);
    } catch (error) {
      console.error(error);
      const errorMsg = { role: 'agent', content: `⚠️ ${error.message || 'Sorry, there was an error processing your request.'}` };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isAuthenticated === null) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div className="activity-indicator">
          <div className="spinner"></div> System Initializing...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div className="control-plane-card" style={{ maxWidth: '400px', textAlign: 'center' }}>
          <Terminal size={48} className="text-orange" style={{ margin: '0 auto 20px' }} />
          <h1 style={{ marginBottom: '10px' }}>Swiggy AI Control Plane</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>
            Authentication required to access MCP orchestration layer.
          </p>
          <a 
            href="/auth/start" 
            style={{ 
              display: 'inline-block', 
              backgroundColor: 'var(--orange-primary)', 
              color: 'white', 
              padding: '12px 24px', 
              borderRadius: '6px', 
              textDecoration: 'none',
              fontWeight: 'bold'
            }}
          >
            Connect Swiggy Account
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <StatusPanel />
      
      <main className="main-content">
        <div className="chat-container">
          <div className="messages-list" ref={messagesListRef}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', marginTop: '100px', color: 'var(--text-secondary)' }}>
                <Terminal size={48} style={{ margin: '0 auto 20px', opacity: 0.5 }} />
                <p>System ready. Awaiting operational parameters.</p>
              </div>
            )}
            
            {messages.map((msg, idx) => (
              <Message 
                key={idx} 
                msg={msg} 
                isLatestAgentMsg={msg.role === 'agent' && idx === messages.length - 1} 
                onAction={handleSend}
              />
            ))}
            
            {isLoading && (
              <div className="activity-indicator">
                <div className="spinner"></div> 
                <span className="typing-text">Processing request...</span>
              </div>
            )}
          </div>
        </div>
      </main>

      <div className="input-container">
        <div style={{ maxWidth: '900px', margin: '0 auto', width: '100%' }}>
          <div className="input-box">
            <input
              type="text"
              className="chat-input"
              placeholder="Enter request (e.g., 'Find me something spicy under ₹300')..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button 
              className="send-button" 
              onClick={handleSend} 
              disabled={!inputValue.trim() || isLoading}
            >
              <Send size={16} />
            </button>
          </div>
          <div style={{ textAlign: 'center', marginTop: '12px', fontSize: '11px', color: 'var(--text-secondary)' }}>
            Powered by <span style={{ fontWeight: 'bold', color: 'var(--orange-primary)' }}>Swiggy MCP</span> &bull; Developed by <span style={{ fontWeight: 'bold' }}>Ketan Chokkara</span>
          </div>
        </div>
      </div>
    </div>
  );
}
