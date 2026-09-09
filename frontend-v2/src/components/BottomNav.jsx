import React from 'react';
import { MessageSquare, Package } from 'lucide-react';

export default function BottomNav({ activeTab = 'chat', onTabChange }) {
  return (
    <nav className="bottom-nav-bar" role="tablist" aria-label="Main Navigation">
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'chat'}
        aria-label="Chat"
        className={`bottom-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
        onClick={() => onTabChange?.('chat')}
      >
        <div className="tab-icon-wrap">
          <MessageSquare size={22} strokeWidth={activeTab === 'chat' ? 2.3 : 1.8} />
          {activeTab === 'chat' && <span className="tab-active-indicator" />}
        </div>
      </button>

      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'orders'}
        aria-label="Orders"
        className={`bottom-tab-btn ${activeTab === 'orders' ? 'active' : ''}`}
        onClick={() => onTabChange?.('orders')}
      >
        <div className="tab-icon-wrap">
          <Package size={22} strokeWidth={activeTab === 'orders' ? 2.3 : 1.8} />
          {activeTab === 'orders' && <span className="tab-active-indicator" />}
        </div>
      </button>
    </nav>
  );
}
