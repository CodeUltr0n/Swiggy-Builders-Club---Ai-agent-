import React, { useState, useEffect, useRef } from 'react';
import StatusPanel from './components/StatusPanel';
import Message from './components/Message';
import { Send, Terminal } from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await fetch('/auth/status');
        const data = await res.json();
        setIsAuthenticated(data.authenticated === true);
      } catch (e) {
        console.error("Auth check failed", e);
        setIsAuthenticated(false);
      }
    };
    checkAuth();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    
    const userMsg = { role: 'user', content: inputValue };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMsg.content,
          context: {
            resolved_address: { id: "home", label: "Home", latitude: 12.9716, longitude: 77.5946 }
          }
        })
      });

      if (res.status === 401) {
        setIsAuthenticated(false);
        setIsLoading(false);
        return;
      }

      const data = await res.json();
      
      const agentMsg = {
        role: 'agent',
        content: data.response,
        active_server: data.active_server,
        rankings: data.rankings,
        tool_calls: data.tool_calls
      };
      
      setMessages(prev => [...prev, agentMsg]);
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'agent', content: "Connection to Control Plane failed." }]);
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
          <div className="messages-list">
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
              />
            ))}
            
            {isLoading && (
              <div className="activity-indicator">
                <div className="spinner"></div> 
                <span className="typing-text">Processing request...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-container">
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
              Powered by <span style={{ fontWeight: 'bold', color: '#fff' }}>Swiggy MCP</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
