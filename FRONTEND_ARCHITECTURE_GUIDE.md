# Swiggy MCP Orchestrator: Comprehensive Frontend Architecture & Codebase Guide

This document is a complete, self-contained guide and source code repository of the frontend system and its integration with the Python FastAPI backend and Swiggy Model Context Protocol (MCP) servers. It contains full architecture explanations, network specifications, data flows, and the **complete source code for every frontend file and stylesheet**.

---

## Table of Contents
1. [Architecture & System Overview](#1-architecture--system-overview)
2. [Frontend-to-Backend Network & API Matrix](#2-frontend-to-backend-network--api-matrix)
3. [State Machines & End-to-End User Flows](#3-state-machines--end-to-end-user-flows)
4. [Design System & Styling Architecture](#4-design-system--styling-architecture)
5. [Complete Source Code — Setup & Root Files](#5-complete-source-code--setup--root-files)
   - `frontend/package.json`
   - `frontend/vite.config.js`
   - `frontend/index.html`
   - `frontend/src/main.jsx`
   - `frontend/src/App.jsx`
6. [Complete Source Code — Core Components (Part 1)](#6-complete-source-code--core-components-part-1)
   - `frontend/src/components/FloatingCartBar.jsx`
   - `frontend/src/components/OrchestrationTimeline.jsx`
7. [Complete Source Code — Core Components (Part 2)](#7-complete-source-code--core-components-part-2)
   - `frontend/src/components/StatusPanel.jsx`
   - `frontend/src/components/ItemDetailModal.jsx`
   - `frontend/src/components/OrdersDrawer.jsx`
8. [Complete Source Code — Core Components (Part 3)](#8-complete-source-code--core-components-part-3)
   - `frontend/src/components/CartDrawer.jsx`
   - `frontend/src/components/Message.jsx`
   - `frontend/src/App.css`
9. [Complete Source Code — Design System & Global Stylesheet](#9-complete-source-code--design-system--global-stylesheet)
   - `frontend/src/index.css`
10. [Operational Guidelines for AI Agents](#10-operational-guidelines-for-ai-agents)

---

## 1. Architecture & System Overview

The Swiggy MCP Control Plane is a conversational commerce web application built with **React 19** and **Vite**, served directly by a **Python FastAPI** backend which orchestrates Swiggy Model Context Protocol (MCP) servers (`food`, `instamart`, `dineout`).

```
┌────────────────────────────────────────────────────────────────────────┐
│                          REACT 19 FRONTEND (Vite)                       │
│                                                                        │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────────┐ │
│  │ StatusPanel  │  │   MessagesList   │  │   Cart & Orders Drawers   │ │
│  │ (GPS & MCP)  │  │ (Cards & Deck)   │  │  (Checkout & Live Track)  │ │
│  └──────┬───────┘  └────────┬─────────┘  └─────────────┬─────────────┘ │
└─────────┼───────────────────┼──────────────────────────┼───────────────┘
          │                   │                          │
          │ HTTP JSON API     │ POST /chat (Context)     │ REST Endpoints
          ▼                   ▼                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (server.py)                     │
│                                                                        │
│  ┌───────────────────────┐             ┌─────────────────────────────┐ │
│  │  Session Cart & Auth  │             │   Orchestrator & Router     │ │
│  │ (OAuth & SQLite DB)   │             │  (Prioritizer + State Mach) │ │
│  └──────────┬────────────┘             └──────────────┬──────────────┘ │
└─────────────┼─────────────────────────────────────────┼────────────────┘
              │                                         │
              ▼                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      SWIGGY MCP SERVERS (JSON-RPC)                     │
│               [food]           [instamart]          [dineout]          │
└────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Characteristics
- **Single-Port Production Serving**: FastAPI mounts `frontend/dist` at `/` using `StaticFiles(directory="frontend/dist", html=True)`.
- **Relative URL Communication**: All `fetch()` calls in the frontend use relative paths (`/chat`, `/cart`, `/orders`, etc.), eliminating CORS friction between development and cloud deployment (e.g. Render).
- **Dynamic Context Injection**: Every user query sent to `/chat` automatically includes the user's active geographic context (GPS coordinates, city, locality, address ID) stored in React state and `localStorage`.

---

## 2. Frontend-to-Backend Network & API Matrix

| Endpoint | Method | Caller Component | Request Payload / Query Params | Expected Response Shape |
| :--- | :--- | :--- | :--- | :--- |
| `/auth/status` | `GET` | `App.jsx` (on load) | None | `{"authenticated": bool, "expires_in_hours": float, "scope": str, "mcp_initialized": bool, "mcp_servers": dict}` |
| `/auth/start` | `GET` | Login Gate Button | None | 302 Redirect to Swiggy OAuth URL |
| `/oauth/callback` | `GET` | OAuth Provider | `?code=...&state=...` | HTML page with auto-redirect to `/` |
| `/mcp/status` | `GET` | `StatusPanel.jsx` (5s poll) | None | `{"status": "initialized", "servers": {"food": "connected", "instamart": "connected", "dineout": "connected"}}` |
| `/addresses` | `GET` | `StatusPanel.jsx` | None | `{"success": true, "data": {"addresses": [{"id": str, "addressLine": str, "city": str, "latitude": num, "longitude": num}]}}` |
| `/chat` | `POST` | `App.jsx` (`handleSend`) | `{"query": str, "context": {"latitude": num, "longitude": num, "city": str, "locality": str, "addressLine": str, "address_id": str, "is_live_gps": bool}}` | `{"status": "ok", "query": str, "response": str, "active_server": str, "tool_calls": [...], "state": {...}, "rankings": [...]}` |
| `/cart` | `GET` | `App.jsx` (`fetchCart`) | `?address_id=...` (optional) | `{"has_items": bool, "items": [...], "item_count": int, "item_total": float, "delivery_fee": float, "taxes": float, "discount": float, "final_amount": float, "applied_coupon": str\|null, "restaurant_id": str, "restaurant_name": str}` |
| `/cart/add` | `POST` | `App.jsx` (`handleAddToCart`) | `{"type": "food"\|"instamart", "restaurant_id": str, "restaurant_name": str, "item_id": str, "name": str, "price": float, "quantity": int, "address_id": str, "is_veg": bool, "image_url": str}` | Returns updated cart bill object |
| `/cart/update` | `POST` | `CartDrawer.jsx` | `{"item_id": str, "quantity": int, "address_id": str}` | Returns updated cart bill object |
| `/cart/clear` | `POST` | `CartDrawer.jsx` | None | Returns cleared cart bill object |
| `/cart/apply-coupon`| `POST`| `CartDrawer.jsx` | `{"coupon_code": str, "address_id": str}` | Returns cart bill with `"message": str` and updated `"discount"` |
| `/cart/checkout` | `POST` | `CartDrawer.jsx` | `{"address_id": str}` | `{"success": true, "order_id": str, "restaurant_name": str, "items": [...], "total_amount": float, "status": "PLACED", "eta": str, "message": str}` |
| `/orders` | `GET` | `OrdersDrawer.jsx` | `?address_id=...` (optional) | `{"orders": [...], "mcp_orders": [...], "total": int}` |
| `/orders/track/{id}`| `GET`| `OrdersDrawer.jsx` | URL path: `order_id` | `{"order_id": str, "status": str, "step": int, "eta": str, "delivery_partner": {"name": str, "rating": str, "phone": str, "vehicle": str}, "steps": [...]}` |

---

## 3. State Machines & End-to-End User Flows

### 3.1 Geolocation Detection & Dynamic Swiggy Registration
1. `StatusPanel` calls `navigator.geolocation.getCurrentPosition()`.
2. Coordinates `(lat, lng)` are reverse-geocoded against OpenStreetMap Nominatim API (`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`).
3. Active location is saved in `localStorage['swiggy_active_location']` and React state.
4. When a user requests dishes, the location is attached to `/chat`. Backend router matches the nearest address (within 3.5km) or dynamically registers a new address on Swiggy via `food:create_address`.

### 3.2 Conversational Search & Interactive Card Deck
1. User types a query (e.g., *"Find spicy chicken biryani near me"*).
2. FastAPI `/chat` routes to `food` MCP server, extracting dishes and restaurants into `tool_calls`.
3. `Message.jsx` parses `msg.tool_calls`, grouping results into segmented tabs: `Dishes`, `Restaurants`, `Instamart`.
4. User can click any card to inspect in `ItemDetailModal` or click **ADD** to directly trigger `POST /cart/add`.

### 3.3 Cart Synchronization & Single-Restaurant Policy
1. `session_cart` enforces Swiggy's single-restaurant constraint: adding food from a different restaurant clears existing items.
2. Item additions asynchronously sync with Swiggy MCP (`food:update_food_cart` or `instamart:update_cart`).
3. Bill calculations compute Item Total, Delivery Fee (Free over ₹500, else ₹35), Taxes & Packing (5%), and Coupon Discount.

---

## 4. Design System & Styling Architecture

The UI implements a custom **Liquid Glass / Glassmorphism** aesthetic defined in `frontend/src/index.css`:
- **Color Tokens**: Swiggy Orange (`#fc8019`, `#ea580c`), Success Green (`#16a34a`), Warning (`#ca8a04`), Error (`#dc2626`).
- **Glass Tokens**: `--panel-bg: rgba(255, 255, 255, 0.25)`, `--surface-bg: rgba(255, 255, 255, 0.15)`, `--border-color: rgba(255, 255, 255, 0.4)`.
- **Refraction & Blur**: 40px backdrop blur (`backdrop-filter: blur(40px)`) over animated gradient blobs (`::before`, `::after`).
- **Micro-animations**: Pulse badges for live GPS and delivery status, smooth stepper progress bars, slide-in drawers, and card hover elevations.

---

## 5. Complete Source Code — Setup & Root Files

### File: `frontend/package.json`
```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "oxlint",
    "preview": "vite preview"
  },
  "dependencies": {
    "lucide-react": "^1.41.0",
    "react": "^19.2.8",
    "react-dom": "^19.2.8",
    "react-markdown": "^10.1.0"
  },
  "devDependencies": {
    "@types/react": "^19.2.18",
    "@types/react-dom": "^19.2.4",
    "@vitejs/plugin-react": "^6.1.0",
    "oxlint": "^1.79.0",
    "vite": "^8.2.2"
  }
}
```

### File: `frontend/vite.config.js`
```javascript
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
})
```

### File: `frontend/index.html`
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Swiggy MCP Orchestrator</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### File: `frontend/src/main.jsx`
```javascript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

### File: `frontend/src/App.jsx`
```javascript
import React, { useState, useEffect, useRef } from 'react';
import StatusPanel from './components/StatusPanel';
import Message from './components/Message';
import FloatingCartBar from './components/FloatingCartBar';
import CartDrawer from './components/CartDrawer';
import OrdersDrawer from './components/OrdersDrawer';
import { Send, Terminal } from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [cart, setCart] = useState({ has_items: false, items: [], item_count: 0, final_amount: 0 });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isOrdersOpen, setIsOrdersOpen] = useState(false);
  const messagesListRef = useRef(null);

  useEffect(() => {
    // Check real auth status on load
    fetch('/auth/status')
      .then(res => res.json())
      .then(data => {
        setIsAuthenticated(data.authenticated);
        if (data.authenticated) {
          fetchCart();
        }
      })
      .catch(() => setIsAuthenticated(false));
  }, []);

  const fetchCart = async () => {
    try {
      const res = await fetch('/cart');
      const data = await res.json();
      setCart(data);
    } catch (err) {
      console.warn('Cart fetch error:', err);
    }
  };

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

  const [activeLocation, setActiveLocation] = useState(() => {
    try {
      const saved = localStorage.getItem('swiggy_active_location');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const handleLocationChange = (newLoc) => {
    setActiveLocation(newLoc);
    try {
      localStorage.setItem('swiggy_active_location', JSON.stringify(newLoc));
    } catch (e) {
      console.warn('Storage error:', e);
    }
  };

  const handleSend = async (actionQuery) => {
    const textToSend = (typeof actionQuery === 'string' ? actionQuery : inputValue).trim();
    if (!textToSend) return;
    
    const userMsg = { role: 'user', content: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const context = {};
      if (activeLocation) {
        if (activeLocation.latitude) context.latitude = activeLocation.latitude;
        if (activeLocation.longitude) context.longitude = activeLocation.longitude;
        if (activeLocation.city) context.city = activeLocation.city;
        if (activeLocation.locality) context.locality = activeLocation.locality;
        if (activeLocation.addressLine) context.addressLine = activeLocation.addressLine;
        if (activeLocation.addressId) context.address_id = activeLocation.addressId;
        if (activeLocation.isLiveGps) context.is_live_gps = true;
      }

      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: textToSend, context })
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

  const handleAddToCart = async (dishOrProd, restaurantName) => {
    try {
      const payload = {
        type: dishOrProd.type || (dishOrProd.brand ? 'instamart' : 'food'),
        restaurant_id: dishOrProd.restaurantId || dishOrProd.restaurant_id || 'rest_1',
        restaurant_name: restaurantName || dishOrProd.restaurantName || 'Restaurant',
        item_id: String(dishOrProd.id || dishOrProd.itemId),
        name: dishOrProd.name,
        price: dishOrProd.price || 0,
        quantity: 1,
        is_veg: dishOrProd.isVeg ?? true,
        image_url: dishOrProd.imageUrl || '',
        address_id: activeLocation?.addressId
      };
      const res = await fetch('/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
      }
    } catch (err) {
      console.error('Failed to add item to cart', err);
    }
  };

  const handleUpdateQuantity = async (itemId, quantity) => {
    try {
      const res = await fetch('/cart/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: String(itemId),
          quantity,
          address_id: activeLocation?.addressId
        })
      });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
      }
    } catch (err) {
      console.error('Failed to update cart quantity', err);
    }
  };

  const handleClearCart = async () => {
    try {
      const res = await fetch('/cart/clear', { method: 'POST' });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
      }
    } catch (err) {
      console.error('Failed to clear cart', err);
    }
  };

  const handleApplyCoupon = async (code) => {
    try {
      const res = await fetch('/cart/apply-coupon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coupon_code: code,
          address_id: activeLocation?.addressId
        })
      });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
        return updatedCart;
      }
    } catch (err) {
      console.error('Failed to apply coupon', err);
    }
  };

  const handleCheckout = async () => {
    const res = await fetch('/cart/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        address_id: activeLocation?.addressId
      })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || 'Failed to place order');
    }
    const orderData = await res.json();
    fetchCart();
    return orderData;
  };

  const handleReorder = async (items, merchantName) => {
    for (const item of items) {
      await handleAddToCart(item, merchantName);
    }
    setIsCartOpen(true);
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
      <StatusPanel 
        activeLocation={activeLocation} 
        onLocationChange={handleLocationChange}
        cartCount={cart?.item_count || 0}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenOrders={() => setIsOrdersOpen(true)}
      />
      
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
                onAddToCart={handleAddToCart}
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

      {/* Floating Bottom Cart Bar */}
      <FloatingCartBar 
        cart={cart} 
        onOpenCart={() => setIsCartOpen(true)} 
      />

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

      {/* Sliding Cart Drawer */}
      <CartDrawer 
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        onUpdateQuantity={handleUpdateQuantity}
        onClearCart={handleClearCart}
        onApplyCoupon={handleApplyCoupon}
        onCheckout={handleCheckout}
        onOpenOrders={() => {
          setIsCartOpen(false);
          setIsOrdersOpen(true);
        }}
      />

      {/* Sliding Orders & Live Tracking Drawer */}
      <OrdersDrawer 
        isOpen={isOrdersOpen}
        onClose={() => setIsOrdersOpen(false)}
        onReorder={handleReorder}
      />
    </div>
  );
}
```

---

## 6. Complete Source Code — Core Components (Part 1)

### File: `frontend/src/components/FloatingCartBar.jsx`
```javascript
import React from 'react';
import { ShoppingBag, ChevronRight } from 'lucide-react';

export default function FloatingCartBar({ cart, onOpenCart }) {
  if (!cart || !cart.has_items || cart.item_count <= 0) {
    return null;
  }

  const itemCount = cart.item_count || cart.items?.length || 0;
  const amount = cart.final_amount || cart.item_total || 0;
  const restaurantName = cart.restaurant_name || (cart.cart_type === 'instamart' ? 'Instamart Store' : 'Swiggy');

  return (
    <div className="floating-cart-wrapper">
      <div className="floating-cart-bar" onClick={onOpenCart}>
        <div className="cart-bar-left">
          <div className="cart-icon-bubble">
            <ShoppingBag size={18} color="white" />
            <span className="cart-badge-count">{itemCount}</span>
          </div>
          <div className="cart-info">
            <span className="cart-count-text">
              {itemCount} {itemCount === 1 ? 'ITEM' : 'ITEMS'}
            </span>
            <span className="cart-dot-divider">•</span>
            <span className="cart-amount-text">₹{amount}</span>
            {restaurantName && (
              <span className="cart-restaurant-name">from {restaurantName}</span>
            )}
          </div>
        </div>

        <button className="cart-view-btn" onClick={(e) => { e.stopPropagation(); onOpenCart(); }}>
          <span>View Cart</span>
          <ChevronRight size={17} />
        </button>
      </div>
    </div>
  );
}
```

### File: `frontend/src/components/OrchestrationTimeline.jsx`
```javascript
import React, { useState, useEffect } from 'react';
import { Activity, CheckCircle2, ChevronRight, Server } from 'lucide-react';

export default function OrchestrationTimeline({ activeServer, rankings, query }) {
  const [stage, setStage] = useState(0);

  // Animate through the stages
  useEffect(() => {
    if (stage < 5) {
      const timer = setTimeout(() => {
        setStage(s => s + 1);
      }, 600); // 600ms per stage for a dramatic effect
      return () => clearTimeout(timer);
    }
  }, [stage]);

  const servers = [
    { name: 'food', label: 'Food MCP', reason: 'High food intent' },
    { name: 'instamart', label: 'Instamart', reason: 'Grocery intent' },
    { name: 'dineout', label: 'Dineout', reason: 'Dining out intent' }
  ];

  // Derive scores from rankings if available, else mock based on activeServer
  const getScore = (serverName) => {
    if (rankings) {
      const r = rankings.find(x => x[0] === serverName);
      if (r) return Math.min(99, Math.round(r[1] * 40)) + '%'; // roughly scale score to percentage
    }
    return serverName === activeServer ? '94%' : (serverName === 'instamart' ? '21%' : '14%');
  };

  const getReason = () => {
    if (activeServer === 'food') return 'High food intent • Dinner time • Current location supports Food';
    if (activeServer === 'instamart') return 'Grocery items detected • High urgency';
    if (activeServer === 'dineout') return 'Table booking request • Evening slot availability';
    return 'Fallback default routing';
  };

  const isComplete = stage >= 5;

  return (
    <div className="control-plane-card">
      <div className="control-plane-header">
        <Activity size={14} className="text-orange" />
        ORCHESTRATOR
      </div>

      <div className="timeline-step">
        <div className="timeline-label">Intent detected</div>
        <div className="timeline-value">
          {stage >= 1 ? <span className="text-orange font-bold">{(activeServer || 'GENERIC').toUpperCase()}_ORDER</span> : '...'}
        </div>
      </div>

      <div className="timeline-step">
        <div className="timeline-label">Context analysis</div>
        <div className="timeline-value">
          {stage >= 2 ? <CheckCircle2 size={14} className="text-orange inline mr-1" /> : '...'}
        </div>
      </div>

      {stage >= 2 && (
        <div style={{ paddingLeft: '140px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
          <div><CheckCircle2 size={12} className="inline mr-1" /> Location</div>
          <div><CheckCircle2 size={12} className="inline mr-1" /> History signal</div>
          <div><CheckCircle2 size={12} className="inline mr-1" /> Time signal</div>
        </div>
      )}

      <div className="timeline-step">
        <div className="timeline-label">Scoring</div>
        <div className="timeline-value">
          {stage >= 3 ? <span className="text-orange">Complete</span> : (stage === 2 ? 'Computing...' : '...')}
        </div>
      </div>

      {stage >= 4 && (
        <div className="routing-container">
          <div className="control-plane-header">
            <Server size={14} /> ROUTING
          </div>
          
          <div style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px' }}>
            {servers.map(s => {
              const isSelected = s.name === activeServer;
              return (
                <div key={s.name} className={`routing-server-row ${isSelected ? 'selected' : ''}`}>
                  <span>{s.label}</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {getScore(s.name)}
                    {isSelected && <span style={{ fontSize: '10px' }}>&larr; SELECTED</span>}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="routing-reasoning">
            <strong>Why {activeServer ? activeServer.charAt(0).toUpperCase() + activeServer.slice(1) : 'this'} MCP?</strong><br />
            {getReason()}
          </div>
        </div>
      )}

      {stage >= 5 && (
        <div style={{ marginTop: '16px', color: 'var(--status-success)', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <ChevronRight size={14} /> Executing {activeServer ? activeServer.toUpperCase() : 'SELECTED'} MCP...
        </div>
      )}

    </div>
  );
}
```

---

## 7. Complete Source Code — Core Components (Part 2)

### File: `frontend/src/components/StatusPanel.jsx`
```javascript
import React, { useEffect, useState, useRef } from 'react';
import { Shield, MapPin, Navigation, Search, Check, X, RefreshCw, ShoppingBag, Package } from 'lucide-react';

export default function StatusPanel({ 
  activeLocation, 
  onLocationChange, 
  cartCount = 0, 
  onOpenCart, 
  onOpenOrders 
}) {
  const [servers, setServers] = useState({
    food: 'pending',
    instamart: 'pending',
    dineout: 'pending'
  });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [isDetectingGps, setIsDetectingGps] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const searchTimeoutRef = useRef(null);

  // 1. Initial Live Location Auto-Detection
  useEffect(() => {
    // If no active location set yet, detect live GPS
    if (!activeLocation) {
      detectLiveGps();
    }
    fetchSavedAddresses();

    // Poll MCP server statuses
    const fetchStatus = async () => {
      try {
        const res = await fetch('/mcp/status');
        const data = await res.json();
        if (data.servers) {
          setServers({
            food: data.servers.food || 'disconnected',
            instamart: data.servers.instamart || 'disconnected',
            dineout: data.servers.dineout || 'disconnected'
          });
        }
      } catch (err) {
        console.error('Failed to fetch status', err);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch saved addresses from Swiggy
  const fetchSavedAddresses = async () => {
    try {
      const res = await fetch('/addresses');
      const data = await res.json();
      const list = data?.data?.addresses || data?.addresses || [];
      setSavedAddresses(list);
      
      // If GPS wasn't detected and no active location, default to first saved address
      if (!activeLocation && list.length > 0) {
        const first = list[0];
        const line = first.addressLine || first.fullAddress || '';
        const parts = line.split(',').map(s => s.trim()).filter(Boolean);
        const label = parts.length > 1 ? `${parts[0]}, ${parts[1]}` : (parts[0] || first.label || 'Saved Address');
        onLocationChange?.({
          label: `${first.addressCategory || 'Saved'}: ${label}`,
          addressLine: line,
          addressId: first.id,
          city: first.city || '',
          isLiveGps: false,
        });
      }
    } catch (e) {
      console.warn('Could not fetch saved addresses:', e);
    }
  };

  // Browser Geolocation Detection
  const detectLiveGps = () => {
    if (!navigator.geolocation) {
      console.warn('Geolocation not supported by browser');
      fetchSavedAddresses();
      return;
    }

    setIsDetectingGps(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,
            { headers: { 'User-Agent': 'SwiggyMCPOrchestrator/1.0' } }
          );
          const geo = await res.json();
          const a = geo.address || {};
          const locality = a.suburb || a.neighbourhood || a.road || a.residential || a.village || a.town || a.city || 'Current Area';
          const city = a.city || a.state_district || a.state || '';
          const displayLabel = city ? `${locality}, ${city}` : locality;
          
          const locObj = {
            label: displayLabel,
            locality: locality,
            city: city,
            addressLine: geo.display_name,
            postalCode: a.postcode || '',
            latitude: lat,
            longitude: lng,
            isLiveGps: true,
          };
          onLocationChange?.(locObj);
        } catch {
          onLocationChange?.({
            label: `GPS (${lat.toFixed(3)}, ${lng.toFixed(3)})`,
            latitude: lat,
            longitude: lng,
            isLiveGps: true,
          });
        } finally {
          setIsDetectingGps(false);
          setIsModalOpen(false);
        }
      },
      (err) => {
        console.warn('Browser geolocation denied or unavailable:', err);
        setIsDetectingGps(false);
        fetchSavedAddresses();
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  // Search places via Nominatim
  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);

    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (!query.trim() || query.length < 3) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&countrycodes=in&limit=4`,
          { headers: { 'User-Agent': 'SwiggyMCPOrchestrator/1.0' } }
        );
        const results = await res.json();
        setSearchResults(results || []);
      } catch (err) {
        console.warn('Place search error:', err);
      } finally {
        setIsSearching(false);
      }
    }, 400);
  };

  const handleSelectSearchResult = (result) => {
    const parts = result.display_name.split(',').map(s => s.trim()).filter(Boolean);
    const shortName = parts.slice(0, 2).join(', ');
    const cityName = parts.find(p => ['Bengaluru', 'Bangalore', 'Hyderabad', 'Mumbai', 'Delhi', 'Vijayawada', 'Amaravati', 'Chennai', 'Pune'].some(c => p.toLowerCase().includes(c.toLowerCase()))) || parts[1] || '';
    
    onLocationChange?.({
      label: shortName,
      locality: parts[0],
      city: cityName,
      addressLine: result.display_name,
      latitude: parseFloat(result.lat),
      longitude: parseFloat(result.lon),
      isLiveGps: false,
    });
    setIsModalOpen(false);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleSelectSavedAddress = (addr) => {
    const line = addr.addressLine || addr.fullAddress || '';
    const parts = line.split(',').map(s => s.trim()).filter(Boolean);
    const label = parts.length > 1 ? `${parts[0]}, ${parts[1]}` : (parts[0] || addr.label || 'Saved Address');
    onLocationChange?.({
      label: `${addr.addressCategory || 'Saved'}: ${label}`,
      addressLine: line,
      addressId: addr.id,
      city: addr.city || '',
      isLiveGps: false,
    });
    setIsModalOpen(false);
  };

  const getStatusClass = (status) => {
    if (status === 'connected') return 'connected';
    if (status === 'degraded') return 'degraded';
    return 'disconnected';
  };

  return (
    <>
      <div className="header-panel">
        <div className="brand-title">
          <Shield size={18} />
          SWIGGY MCP CONTROL PLANE
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', justifyContent: 'center' }}>
          {/* Interactive Location Pill */}
          <button 
            type="button"
            className="location-pill location-pill-interactive" 
            title="Click to detect live GPS or choose delivery location"
            onClick={() => setIsModalOpen(true)}
          >
            {activeLocation?.isLiveGps ? (
              <span className="live-dot" title="Live GPS Active" />
            ) : (
              <MapPin size={13} color="#ea580c" />
            )}
            <span className="location-pill-text">
              {activeLocation?.label || (isDetectingGps ? 'Detecting Live GPS...' : 'Select Location')}
            </span>
            <span className="location-change-tag">Change</span>
          </button>

          <div className="mcp-status-group">
            {Object.entries(servers).map(([name, status]) => (
              <div key={name} className="mcp-status-item">
                <div className={`status-dot ${getStatusClass(status)}`}></div>
                <span style={{ textTransform: 'capitalize' }}>{name}</span>
              </div>
            ))}
          </div>

          {/* Quick Nav: Orders & Cart Buttons */}
          <div className="header-actions-group">
            <button 
              type="button" 
              className="header-action-btn"
              onClick={onOpenOrders}
              title="Track live and past orders"
            >
              <Package size={15} color="var(--text-secondary)" />
              <span>Orders</span>
            </button>

            <button 
              type="button" 
              className={`header-action-btn cart-header-btn ${cartCount > 0 ? 'has-items' : ''}`}
              onClick={onOpenCart}
              title="View your Swiggy cart"
            >
              <ShoppingBag size={15} />
              <span>Cart</span>
              {cartCount > 0 && (
                <span className="header-cart-badge">{cartCount}</span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Location Selector Modal */}
      {isModalOpen && (
        <div className="location-modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="location-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="location-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Navigation size={18} color="#ea580c" />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>Choose Delivery Location</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setIsModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="location-modal-body">
              {/* Option 1: Live GPS Detection */}
              <button 
                type="button" 
                className="live-detect-action-btn"
                onClick={detectLiveGps}
                disabled={isDetectingGps}
              >
                <div className="live-detect-icon-wrapper">
                  <Navigation size={16} className={isDetectingGps ? 'spin' : ''} />
                </div>
                <div style={{ textAlign: 'left', flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    Detect My Current Location
                    <span className="live-badge">GPS</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    Using your device's live hardware location
                  </div>
                </div>
                {activeLocation?.isLiveGps && <Check size={16} color="#10b981" />}
              </button>

              {/* Option 2: Search Custom Location */}
              <div style={{ marginTop: '14px' }}>
                <div className="location-search-box">
                  <Search size={14} color="#94a3b8" />
                  <input
                    type="text"
                    placeholder="Search city, area or street (e.g. Indiranagar, Bengaluru)..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    className="location-search-input"
                  />
                  {isSearching && <RefreshCw size={14} className="spin" color="#ea580c" />}
                </div>

                {searchResults.length > 0 && (
                  <div className="location-search-results">
                    {searchResults.map((r, idx) => (
                      <div 
                        key={idx} 
                        className="location-search-item"
                        onClick={() => handleSelectSearchResult(r)}
                      >
                        <MapPin size={13} color="#ea580c" style={{ flexShrink: 0, marginTop: '2px' }} />
                        <span style={{ fontSize: '12px', lineHeight: '1.4' }}>{r.display_name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Option 3: Saved Swiggy Addresses */}
              {savedAddresses.length > 0 && (
                <div style={{ marginTop: '16px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.5px' }}>
                    Saved Swiggy Addresses ({savedAddresses.length})
                  </div>
                  <div className="saved-addresses-list">
                    {savedAddresses.map((addr) => {
                      const isSelected = activeLocation?.addressId === addr.id;
                      return (
                        <div 
                          key={addr.id}
                          className={`saved-address-card ${isSelected ? 'selected' : ''}`}
                          onClick={() => handleSelectSavedAddress(addr)}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span className="address-category-tag">{addr.addressCategory || addr.label || 'Home'}</span>
                            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                              {addr.userName ? `${addr.userName} • ` : ''}{addr.addressTag || 'Delivery'}
                            </span>
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: '1.3' }}>
                            {addr.addressLine || addr.fullAddress}
                          </div>
                          {isSelected && (
                            <div className="selected-indicator">
                              <Check size={12} color="#fff" />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

### File: `frontend/src/components/ItemDetailModal.jsx`
```javascript
import React from 'react';
import { X, Star, Clock, MapPin, ShoppingBag, Utensils, Calendar, Plus, Tag, ShieldCheck } from 'lucide-react';

const FALLBACK_FOOD_IMG = 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=660&auto=format&fit=crop&q=80';
const FALLBACK_REST_IMG = 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=660&auto=format&fit=crop&q=80';
const FALLBACK_GROCERY_IMG = 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=660&auto=format&fit=crop&q=80';

export default function ItemDetailModal({ item, type, onClose, onAction, onAddToCart }) {
  if (!item) return null;

  const isProduct = type === 'product';
  const isDineout = type === 'dineout';
  const isFood = type === 'food';
  const isDish = type === 'dish';

  const title = item.name || item.displayName || 'Details';
  const subtitle = item.restaurantName || item.cuisine || item.brand || item.category || (isDineout ? 'Dining & Table Reservation' : 'Swiggy');
  const rating = item.rating || item.avgRating || '4.2';
  const distance = item.distance_km ? `${item.distance_km} km` : (item.distanceKm ? `${item.distanceKm} km` : '');
  const locality = item.locality || item.area || '';
  const price = item.price || item.costForTwo || item.avg_cost_for_two || '';
  const mrp = item.mrp;
  const sla = item.sla || (isProduct ? '15-25 mins' : '30-40 mins');
  const menuHighlights = item.menu_highlights || [];

  const fallbackImg = isDineout ? FALLBACK_REST_IMG : (isProduct ? FALLBACK_GROCERY_IMG : FALLBACK_FOOD_IMG);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
          <X size={18} />
        </button>

        <div className="modal-image-container">
          <img 
            src={item.imageUrl || fallbackImg} 
            alt={title} 
            className="modal-image" 
            onError={(e) => { 
              e.target.onerror = null;
              e.target.src = fallbackImg;
            }} 
          />
          {item.offer && <span className="modal-badge">{item.offer}</span>}
        </div>

        <div className="modal-content">
          <div className="modal-header">
            <div>
              <h2 className="modal-title">{title}</h2>
              {subtitle && <p className="modal-subtitle">{subtitle}</p>}
            </div>
            <div className="modal-rating">
              <Star size={14} fill="#b45309" color="#b45309" />
              <span>{rating}</span>
            </div>
          </div>

          <div className="modal-meta-row">
            {distance && (
              <span className="meta-pill">
                <MapPin size={13} /> {distance}
              </span>
            )}
            {locality && (
              <span className="meta-pill">
                <MapPin size={13} /> {locality}
              </span>
            )}
            {sla && (
              <span className="meta-pill">
                <Clock size={13} /> {sla} {typeof sla === 'number' ? 'mins' : ''}
              </span>
            )}
            {item.quantity && (
              <span className="meta-pill">
                <Tag size={13} /> {item.quantity}
              </span>
            )}
            <span className="meta-pill certified">
              <ShieldCheck size={13} /> Verified Swiggy MCP
            </span>
          </div>

          {/* Pricing Row for Products & Dishes */}
          {(isProduct || isDish) && (
            <div className="modal-pricing-box">
              <div className="pricing-info">
                <span className="current-price">₹{price}</span>
                {mrp && mrp > price && (
                  <>
                    <span className="mrp-price">₹{mrp}</span>
                    <span className="discount-tag">
                      {Math.round(((mrp - price) / mrp) * 100)}% OFF
                    </span>
                  </>
                )}
              </div>
              <span className="stock-status in-stock">⚡ Fresh & Available to Order</span>
            </div>
          )}

          {item.description && (
            <div className="modal-section" style={{ marginTop: '12px' }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.6 }}>
                {item.description}
              </p>
            </div>
          )}

          {/* Dining Cost for Dineout */}
          {isDineout && (
            <div className="modal-pricing-box">
              <div className="pricing-info">
                <span className="current-price">{price}</span>
                <span className="mrp-price" style={{ textDecoration: 'none', color: 'var(--text-secondary)' }}>approx cost for two</span>
              </div>
              <span className="stock-status in-stock">Instant Confirmation</span>
            </div>
          )}

          {/* Menu Highlights for Food Restaurants */}
          {isFood && menuHighlights.length > 0 && (
            <div className="modal-section">
              <h3 className="section-title">Popular Items & Highlights</h3>
              <div className="popular-items-list">
                {menuHighlights.map((dish, i) => (
                  <div key={i} className="popular-item-row">
                    <span className="dish-name">{dish}</span>
                    <button
                      className="add-dish-btn"
                      onClick={() => {
                        const cleanDish = dish.replace(/\s*\(₹[0-9.]+\)/, '').trim();
                        const priceMatch = dish.match(/₹([0-9.]+)/);
                        const dishPrice = priceMatch ? parseFloat(priceMatch[1]) : 150;
                        if (onAddToCart) {
                          onAddToCart({
                            id: `highlight_${i}_${item.id}`,
                            name: cleanDish,
                            price: dishPrice,
                            is_veg: true,
                            restaurant_id: item.id,
                            restaurant_name: title
                          }, title);
                        } else {
                          onAction(`order ${cleanDish} from ${title}`);
                        }
                        onClose();
                      }}
                    >
                      <Plus size={13} /> Add to Cart
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Bottom CTA Action Buttons */}
          <div className="modal-footer">
            {isDish && (
              <button
                className="modal-primary-btn orange"
                onClick={() => {
                  if (onAddToCart) {
                    onAddToCart(item, item.restaurantName);
                  } else {
                    onAction(`order ${title}`);
                  }
                  onClose();
                }}
              >
                <Plus size={18} /> Add to Cart (₹{price})
              </button>
            )}

            {isProduct && (
              <button
                className="modal-primary-btn green"
                onClick={() => {
                  if (onAddToCart) {
                    onAddToCart({
                      id: item.id,
                      name: title,
                      price: price,
                      is_veg: true,
                      type: 'instamart'
                    }, 'Instamart Store');
                  } else {
                    onAction(`add 1 ${title}`);
                  }
                  onClose();
                }}
              >
                <ShoppingBag size={17} /> Add to Cart (₹{price})
              </button>
            )}

            {isFood && (
              <div className="btn-group">
                <button
                  className="modal-secondary-btn"
                  onClick={() => {
                    onAction(`show menu for ${title}`);
                    onClose();
                  }}
                >
                  <Utensils size={15} /> View Full Menu
                </button>
                <button
                  className="modal-primary-btn orange"
                  onClick={() => {
                    onAction(`order from ${title}`);
                    onClose();
                  }}
                >
                  <ShoppingBag size={17} /> Order Food
                </button>
              </div>
            )}

            {isDineout && (
              <button
                className="modal-primary-btn purple"
                onClick={() => {
                  onAction(`book a table at ${title} for 2 guests`);
                  onClose();
                }}
              >
                <Calendar size={17} /> Book Table (2 Guests)
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

### File: `frontend/src/components/OrdersDrawer.jsx`
```javascript
import React, { useState, useEffect } from 'react';
import { 
  X, Package, Clock, CheckCircle2, Bike, Phone, MapPin, 
  RotateCcw, ChevronRight, ShieldCheck, Utensils, ShoppingBag 
} from 'lucide-react';

export default function OrdersDrawer({ isOpen, onClose, onReorder }) {
  const [ordersData, setOrdersData] = useState({ orders: [], mcp_orders: [] });
  const [activeTracking, setActiveTracking] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      fetchOrders();
    }
  }, [isOpen]);

  const fetchOrders = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/orders');
      const data = await res.json();
      setOrdersData(data);

      // If there are orders, pick the latest one for live tracking
      const all = [...(data.orders || []), ...(data.mcp_orders || [])];
      if (all.length > 0) {
        const latestId = all[0].id || all[0].order_id || all[0].orderId;
        if (latestId) {
          fetchTracking(latestId);
        }
      }
    } catch (err) {
      console.error('Failed to load orders', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTracking = async (orderId) => {
    try {
      const res = await fetch(`/orders/track/${orderId}`);
      const data = await res.json();
      setActiveTracking(data);
    } catch (err) {
      console.error('Failed to load tracking', err);
    }
  };

  if (!isOpen) return null;

  const allOrders = ordersData.orders || [];

  return (
    <div className="modal-backdrop cart-backdrop" onClick={onClose}>
      <div className="cart-drawer orders-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="cart-drawer-header">
          <div className="cart-header-title-box">
            <div className="cart-header-icon orange">
              <Package size={20} color="var(--orange-primary)" />
            </div>
            <div>
              <h2 className="cart-drawer-title">Live Orders & History</h2>
              <span className="cart-restaurant-sub">
                Track active deliveries in real-time
              </span>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close orders">
            <X size={20} />
          </button>
        </div>

        <div className="cart-drawer-body">
          {isLoading ? (
            <div className="activity-indicator" style={{ padding: '40px 0', textAlign: 'center' }}>
              <div className="spinner"></div>
              <span>Fetching your Swiggy orders...</span>
            </div>
          ) : allOrders.length === 0 ? (
            <div className="empty-cart-state">
              <div className="empty-icon-wrap">
                <Package size={48} color="var(--text-secondary)" style={{ opacity: 0.4 }} />
              </div>
              <h3>No past orders yet</h3>
              <p>Place your first order using Swiggy MCP to track live deliveries here.</p>
              <button className="cart-browse-btn" onClick={onClose}>
                Order Food Now
              </button>
            </div>
          ) : (
            <div className="orders-scroll-container">
              {/* Active Order Live Tracker Card */}
              {activeTracking && (
                <div className="live-tracking-card">
                  <div className="tracking-card-header">
                    <div>
                      <span className="live-pulse-badge">
                        <span className="pulse-dot"></span> LIVE TRACKING
                      </span>
                      <h3 className="tracking-order-title">
                        Order #{activeTracking.order_id}
                      </h3>
                    </div>
                    <div className="tracking-eta-box">
                      <Clock size={16} color="var(--orange-primary)" />
                      <span className="eta-text">{activeTracking.eta || '24 mins'}</span>
                    </div>
                  </div>

                  {/* 4-Step Progress Stepper */}
                  <div className="tracking-stepper">
                    {[
                      { label: 'Order Confirmed', step: 1, done: true },
                      { label: 'Food Preparing', step: 2, done: (activeTracking.step || 2) >= 2, active: (activeTracking.step || 2) === 2 },
                      { label: 'Out for Delivery', step: 3, done: (activeTracking.step || 2) >= 3, active: (activeTracking.step || 2) === 3 },
                      { label: 'Delivered', step: 4, done: (activeTracking.step || 2) >= 4 }
                    ].map((st, i) => (
                      <div key={i} className={`step-item ${st.done ? 'completed' : ''} ${st.active ? 'current' : ''}`}>
                        <div className="step-circle">
                          {st.done && !st.active ? <CheckCircle2 size={14} /> : st.step}
                        </div>
                        <span className="step-label">{st.label}</span>
                      </div>
                    ))}
                  </div>

                  {/* Delivery Partner Details */}
                  {activeTracking.delivery_partner && (
                    <div className="rider-card">
                      <div className="rider-avatar">
                        <Bike size={20} color="white" />
                      </div>
                      <div className="rider-info">
                        <div className="rider-name">
                          {activeTracking.delivery_partner.name}
                          <span className="rider-rating">{activeTracking.delivery_partner.rating}</span>
                        </div>
                        <div className="rider-vehicle">
                          {activeTracking.delivery_partner.vehicle} &bull; Delivery Partner
                        </div>
                      </div>
                      <a 
                        href={`tel:${activeTracking.delivery_partner.phone}`} 
                        className="rider-call-btn" 
                        title="Call delivery partner"
                      >
                        <Phone size={15} />
                      </a>
                    </div>
                  )}
                </div>
              )}

              {/* Order History Section */}
              <div className="past-orders-section">
                <h4 className="orders-section-heading">Recent Orders ({allOrders.length})</h4>
                
                {allOrders.map((ord, idx) => {
                  const items = ord.items || [];
                  return (
                    <div key={ord.id || idx} className="past-order-card">
                      <div className="past-order-header">
                        <div>
                          <span className="past-order-merchant">{ord.merchant_name || 'Swiggy Food'}</span>
                          <span className="past-order-time">{ord.timestamp || 'Recent'}</span>
                        </div>
                        <span className="order-status-pill">{ord.status || 'PLACED'}</span>
                      </div>

                      <div className="past-order-items">
                        {items.map((it, i) => (
                          <div key={i} className="past-item-line">
                            <span>{it.quantity || 1}x {it.name || 'Item'}</span>
                            <span>₹{it.price || it.total_price || 0}</span>
                          </div>
                        ))}
                      </div>

                      <div className="past-order-footer">
                        <div className="past-order-total">
                          <span>Total Amount</span>
                          <strong>₹{ord.total_amount || 0}</strong>
                        </div>

                        <button 
                          className="reorder-btn"
                          onClick={() => {
                            if (onReorder) {
                              onReorder(items, ord.merchant_name);
                            }
                            onClose();
                          }}
                        >
                          <RotateCcw size={13} />
                          <span>Reorder</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

---

## 8. Complete Source Code — Core Components (Part 3)

### File: `frontend/src/components/CartDrawer.jsx`
```javascript
import React, { useState } from 'react';
import { 
  X, Trash2, Plus, Minus, Tag, ArrowRight, ShieldCheck, 
  Clock, MapPin, CheckCircle2, ShoppingBag, AlertCircle 
} from 'lucide-react';

export default function CartDrawer({
  isOpen,
  onClose,
  cart,
  onUpdateQuantity,
  onClearCart,
  onApplyCoupon,
  onCheckout,
  onOpenOrders,
}) {
  const [couponCode, setCouponCode] = useState('');
  const [couponMsg, setCouponMsg] = useState(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [placedOrder, setPlacedOrder] = useState(null);

  if (!isOpen) return null;

  const items = cart?.items || [];
  const itemCount = cart?.item_count || items.length || 0;
  const itemTotal = cart?.item_total || 0;
  const deliveryFee = cart?.delivery_fee || 0;
  const taxes = cart?.taxes || 0;
  const discount = cart?.discount || 0;
  const finalAmount = cart?.final_amount || 0;
  const restaurantName = cart?.restaurant_name || (cart?.cart_type === 'instamart' ? 'Instamart Store' : 'Swiggy');

  const handleApplyCoupon = async (e) => {
    e.preventDefault();
    if (!couponCode.trim()) return;
    const res = await onApplyCoupon(couponCode.trim());
    if (res?.message) {
      setCouponMsg({ type: 'success', text: res.message });
    } else {
      setCouponMsg({ type: 'success', text: `Coupon ${couponCode.toUpperCase()} applied!` });
    }
  };

  const handleProceedCheckout = async () => {
    setIsCheckingOut(true);
    try {
      const order = await onCheckout();
      setPlacedOrder(order);
    } catch (err) {
      setCouponMsg({ type: 'error', text: err.message || 'Checkout failed. Please try again.' });
    } finally {
      setIsCheckingOut(false);
    }
  };

  return (
    <div className="modal-backdrop cart-backdrop" onClick={onClose}>
      <div className="cart-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="cart-drawer-header">
          <div className="cart-header-title-box">
            <div className="cart-header-icon">
              <ShoppingBag size={20} color="var(--orange-primary)" />
            </div>
            <div>
              <h2 className="cart-drawer-title">Your Cart</h2>
              <span className="cart-restaurant-sub">
                {restaurantName} ({itemCount} {itemCount === 1 ? 'item' : 'items'})
              </span>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close cart">
            <X size={20} />
          </button>
        </div>

        {placedOrder ? (
          /* Order Placed Success View */
          <div className="cart-success-view">
            <div className="success-icon-bubble">
              <CheckCircle2 size={54} color="#16a34a" />
            </div>
            <h3 className="success-title">Order Placed Successfully!</h3>
            <p className="success-sub">
              Your order from <strong>{placedOrder.restaurant_name || restaurantName}</strong> is confirmed via Swiggy MCP.
            </p>
            
            <div className="order-summary-card">
              <div className="order-summary-row">
                <span>Order ID</span>
                <span className="order-code">#{placedOrder.order_id}</span>
              </div>
              <div className="order-summary-row">
                <span>Total Paid (COD)</span>
                <span className="order-total-val">₹{placedOrder.total_amount || finalAmount}</span>
              </div>
              <div className="order-summary-row">
                <span>Estimated Delivery</span>
                <span className="order-eta-val">⚡ {placedOrder.eta || '25-35 mins'}</span>
              </div>
            </div>

            <div className="success-actions">
              <button 
                className="cart-checkout-btn primary"
                onClick={() => {
                  onClose();
                  onOpenOrders && onOpenOrders();
                }}
              >
                <span>Track Live Order</span>
                <ArrowRight size={18} />
              </button>
              <button className="cart-clear-btn" onClick={onClose}>
                Continue Browsing
              </button>
            </div>
          </div>
        ) : items.length === 0 ? (
          /* Empty Cart State */
          <div className="empty-cart-state">
            <div className="empty-icon-wrap">
              <ShoppingBag size={48} color="var(--text-secondary)" style={{ opacity: 0.4 }} />
            </div>
            <h3>Your cart is empty</h3>
            <p>Explore food menus or Instamart groceries and add items to your cart.</p>
            <button className="cart-browse-btn" onClick={onClose}>
              Browse Dishes & Menu
            </button>
          </div>
        ) : (
          /* Cart Items & Bill Breakdown */
          <div className="cart-drawer-body">
            {/* Delivery details header pill */}
            <div className="cart-delivery-pill">
              <Clock size={15} color="var(--orange-primary)" />
              <span>Delivery in <strong>25-35 mins</strong> to your location</span>
            </div>

            {/* Items List */}
            <div className="cart-items-scroll">
              {items.map((item, idx) => (
                <div key={item.id || idx} className="cart-item-row">
                  {/* Veg / Non-Veg Indicator */}
                  <div className={`veg-indicator ${item.is_veg ? 'veg' : 'non-veg'}`}>
                    <span className="veg-dot"></span>
                  </div>

                  <div className="cart-item-details">
                    <span className="cart-item-name">{item.name}</span>
                    <span className="cart-item-unit-price">₹{item.price}</span>
                  </div>

                  {/* Quantity Stepper */}
                  <div className="cart-qty-stepper">
                    <button 
                      className="qty-btn"
                      onClick={() => onUpdateQuantity(item.id, (item.quantity || 1) - 1)}
                      title="Decrease quantity"
                    >
                      {item.quantity === 1 ? <Trash2 size={13} color="#ef4444" /> : <Minus size={13} />}
                    </button>
                    <span className="qty-number">{item.quantity}</span>
                    <button 
                      className="qty-btn"
                      onClick={() => onUpdateQuantity(item.id, (item.quantity || 1) + 1)}
                      title="Increase quantity"
                    >
                      <Plus size={13} />
                    </button>
                  </div>

                  {/* Total item price */}
                  <div className="cart-item-total">
                    ₹{Math.round((item.price * (item.quantity || 1)) * 100) / 100}
                  </div>
                </div>
              ))}
            </div>

            {/* Coupon Box */}
            <div className="cart-coupon-section">
              <form onSubmit={handleApplyCoupon} className="coupon-input-group">
                <Tag size={16} color="var(--orange-primary)" />
                <input 
                  type="text" 
                  placeholder="Enter coupon (e.g. SWIGGY50)"
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value)}
                  className="coupon-input"
                />
                <button type="submit" className="coupon-apply-btn">
                  Apply
                </button>
              </form>
              {couponMsg && (
                <div className={`coupon-msg ${couponMsg.type}`}>
                  {couponMsg.text}
                </div>
              )}
              {cart?.applied_coupon && (
                <div className="active-coupon-tag">
                  <span>Coupon <strong>{cart.applied_coupon}</strong> applied (-₹{discount})</span>
                  <button 
                    className="remove-coupon-btn" 
                    onClick={() => onApplyCoupon('')}
                    title="Remove coupon"
                  >
                    <X size={12} />
                  </button>
                </div>
              )}
            </div>

            {/* Bill Details */}
            <div className="cart-bill-section">
              <h4 className="bill-title">Bill Details</h4>
              <div className="bill-row">
                <span>Item Total</span>
                <span>₹{itemTotal}</span>
              </div>
              <div className="bill-row">
                <span>Delivery Fee</span>
                <span>{deliveryFee === 0 ? <span className="free-tag">FREE</span> : `₹${deliveryFee}`}</span>
              </div>
              <div className="bill-row">
                <span>Taxes and Packing Charges</span>
                <span>₹{taxes}</span>
              </div>
              {discount > 0 && (
                <div className="bill-row discount">
                  <span>Coupon Discount</span>
                  <span>-₹{discount}</span>
                </div>
              )}
              <div className="bill-divider"></div>
              <div className="bill-row total">
                <span>TO PAY</span>
                <span className="final-total">₹{finalAmount}</span>
              </div>
            </div>

            {/* Security Guarantee */}
            <div className="cart-assurance">
              <ShieldCheck size={16} color="#16a34a" />
              <span>100% Genuine Swiggy MCP Checkout • Cash on Delivery</span>
            </div>

            {/* Drawer Footer CTA */}
            <div className="cart-drawer-footer">
              <button className="cart-clear-btn" onClick={onClearCart}>
                Clear Cart
              </button>
              <button 
                className="cart-checkout-btn" 
                onClick={handleProceedCheckout}
                disabled={isCheckingOut}
              >
                {isCheckingOut ? (
                  <span className="checkout-spinner">Placing Order...</span>
                ) : (
                  <>
                    <span>Proceed to Pay (₹{finalAmount})</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

### File: `frontend/src/components/Message.jsx`
```javascript
import React, { useState } from 'react';
import OrchestrationTimeline from './OrchestrationTimeline';
import ItemDetailModal from './ItemDetailModal';
import ReactMarkdown from 'react-markdown';
import { Bot, User, Plus, ShoppingBag, Utensils, Calendar, Info, Check, X } from 'lucide-react';

export const FALLBACK_FOOD_IMG = 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=660&auto=format&fit=crop&q=80';
export const FALLBACK_REST_IMG = 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=660&auto=format&fit=crop&q=80';
export const FALLBACK_GROCERY_IMG = 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=660&auto=format&fit=crop&q=80';

export default function Message({ msg, isLatestAgentMsg, onAction, onAddToCart }) {
  const isAgent = msg.role === 'agent';
  const [activeModalItem, setActiveModalItem] = useState(null);
  const [modalType, setModalType] = useState('food');

  // Extract restaurants, dishes, and products from tool calls to render rich cards if available
  let restaurants = [];
  let dishes = [];
  let products = [];
  let isDineoutServer = msg.active_server === 'dineout';

  if (isAgent && msg.tool_calls) {
    // 1. Extract Dishes
    const dishTool = msg.tool_calls.find(t => t.tool === 'restaurant_menu_dishes');
    if (dishTool && dishTool.result?.data?.dishes) {
      dishes = dishTool.result.data.dishes;
    }

    // 2. Extract Restaurants (search across all matching tool calls)
    const restaurantTools = msg.tool_calls.filter(t => t.tool === 'search_restaurants' || t.tool === 'search_restaurants_dineout');
    for (const searchRes of restaurantTools) {
      if (!searchRes?.result) continue;
      if (searchRes.tool === 'search_restaurants_dineout') {
        isDineoutServer = true;
      }
      let d = searchRes.result.data;
      if (typeof d === 'string') {
        try { d = JSON.parse(d); } catch (e) {}
      }
      const s = searchRes.result.structured;
      let foundRests = [];
      if (Array.isArray(d)) {
        foundRests = d;
      } else if (d && Array.isArray(d.restaurants)) {
        foundRests = d.restaurants;
        if (!dishes.length && Array.isArray(d.dishes)) {
          dishes = d.dishes;
        }
      } else if (s && Array.isArray(s.restaurants)) {
        foundRests = s.restaurants;
        if (!dishes.length && Array.isArray(s.dishes)) {
          dishes = s.dishes;
        }
      }
      if (foundRests.length > 0) {
        restaurants = foundRests;
        break;
      }
    }

    // 3. Extract Instamart Products
    const prodRes = msg.tool_calls.find(t => t.tool === 'search_products');
    if (prodRes && prodRes.result) {
      const d = prodRes.result.data;
      const s = prodRes.result.structured;
      const rawList = Array.isArray(d) ? d : (d?.products || s?.products || []);
      if (Array.isArray(rawList)) {
        products = rawList.map(p => {
          const firstVar = Array.isArray(p.variations) && p.variations.length > 0 ? p.variations[0] : {};
          const pVal = p.price?.offerPrice || p.price?.mrp || firstVar.price?.offerPrice || firstVar.price?.mrp || p.price || 0;
          return {
            ...p,
            name: p.displayName || p.name || firstVar.displayName || 'Grocery Item',
            brand: p.brand || firstVar.brandName || '',
            price: pVal,
            mrp: p.price?.mrp || firstVar.price?.mrp || p.mrp,
            imageUrl: firstVar.imageUrl || p.imageUrl || '',
            quantity: firstVar.quantityDescription || p.quantity || '',
            sla: firstVar.sla?.value || p.sla || '20 mins'
          };
        });
      }
    }
  }

  // Segmented Tab Management: strictly ONE card section at a time fulfilling MCP Orchestration Motto
  const hasDishes = dishes.length > 0;
  const hasRestaurants = restaurants.length > 0;
  const hasProducts = products.length > 0;
  const hasAnyCards = hasDishes || hasRestaurants || hasProducts;

  // Default priority: Dishes > Restaurants > Products (unless dineout, then Restaurants)
  const defaultTab = isDineoutServer && hasRestaurants ? 'restaurants' : (hasDishes ? 'dishes' : (hasRestaurants ? 'restaurants' : 'products'));
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [selectedRestFilter, setSelectedRestFilter] = useState(null);

  // Resolved current tab ensuring we don't display an empty tab
  let currentTab = activeTab;
  if (currentTab === 'dishes' && !hasDishes) {
    currentTab = hasRestaurants ? 'restaurants' : (hasProducts ? 'products' : null);
  } else if (currentTab === 'restaurants' && !hasRestaurants) {
    currentTab = hasDishes ? 'dishes' : (hasProducts ? 'products' : null);
  } else if (currentTab === 'products' && !hasProducts) {
    currentTab = hasDishes ? 'dishes' : (hasRestaurants ? 'restaurants' : null);
  }

  // Extract unique restaurant names from dishes for filter pills
  const dishRestaurantNames = Array.from(
    new Set(dishes.map(d => d.restaurantName).filter(Boolean))
  );

  // Filtered dishes based on restaurant selection
  const displayedDishes = selectedRestFilter 
    ? dishes.filter(d => d.restaurantName === selectedRestFilter)
    : dishes;

  // Detect confirmation state to show interactive [Confirm] / [Cancel] buttons
  const isConfirmPrompt = isAgent && isLatestAgentMsg && (
    msg.content.includes('(yes/no)') ||
    msg.content.includes('Reply **yes** or **no**') ||
    msg.content.includes('Confirm placing this order?') ||
    msg.content.includes('Confirm booking?')
  );

  return (
    <div className={`message-row ${isAgent ? 'agent' : 'user'}`}>
      {isAgent && (
        <div style={{ marginRight: '16px', marginTop: '12px' }}>
          <div style={{ backgroundColor: 'var(--orange-primary)', padding: '8px', borderRadius: '50%' }}>
            <Bot size={20} color="white" />
          </div>
        </div>
      )}
      
      <div className="message-bubble">
        {isAgent && isLatestAgentMsg && msg.rankings && (
          <OrchestrationTimeline 
            activeServer={msg.active_server} 
            rankings={msg.rankings} 
            query={msg.content} 
          />
        )}
        
        <div className="agent-text-content">
          {isAgent ? (
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          ) : (
            msg.content
          )}
        </div>

        {/* Quick action buttons for confirmation flows */}
        {isConfirmPrompt && (
          <div className="quick-actions-bar">
            <button 
              className="quick-action-btn confirm"
              onClick={() => onAction && onAction('yes')}
            >
              <Check size={16} /> Confirm (Yes)
            </button>
            <button 
              className="quick-action-btn cancel"
              onClick={() => onAction && onAction('no')}
            >
              <X size={16} /> Cancel (No)
            </button>
          </div>
        )}

        {/* Single Unified Interactive Card Deck (Fulfilling MCP Orchestration Motto) */}
        {hasAnyCards && (
          <div className="unified-card-deck">
            {/* Tab Header if multiple entity types exist */}
            {( (hasDishes && hasRestaurants) || (hasDishes && hasProducts) || (hasRestaurants && hasProducts) ) && (
              <div className="deck-header-bar">
                <div className="deck-tabs-pills">
                  {hasDishes && (
                    <button 
                      className={`deck-tab-pill ${currentTab === 'dishes' ? 'active' : ''}`}
                      onClick={() => setActiveTab('dishes')}
                    >
                      <Utensils size={13} />
                      <span>Dishes ({dishes.length})</span>
                    </button>
                  )}
                  {hasRestaurants && (
                    <button 
                      className={`deck-tab-pill ${currentTab === 'restaurants' ? 'active' : ''}`}
                      onClick={() => setActiveTab('restaurants')}
                    >
                      <ShoppingBag size={13} />
                      <span>Restaurants ({restaurants.length})</span>
                    </button>
                  )}
                  {hasProducts && (
                    <button 
                      className={`deck-tab-pill ${currentTab === 'products' ? 'active' : ''}`}
                      onClick={() => setActiveTab('products')}
                    >
                      <span>Instamart ({products.length})</span>
                    </button>
                  )}
                </div>

                <span className="deck-subtitle-hint">
                  {currentTab === 'dishes' && 'Real Swiggy Menu • Instant Add to Cart'}
                  {currentTab === 'restaurants' && (isDineoutServer ? 'Reserve Tables' : 'Delivering Near You')}
                  {currentTab === 'products' && 'Instant Grocery Delivery'}
                </span>
              </div>
            )}

            {/* Restaurant Filter Chips when viewing dishes from multiple restaurants */}
            {currentTab === 'dishes' && dishRestaurantNames.length > 1 && (
              <div className="deck-filter-row">
                <span className="deck-filter-label">Filter:</span>
                <div className="deck-filter-chips">
                  <button 
                    className={`filter-chip ${selectedRestFilter === null ? 'active' : ''}`}
                    onClick={() => setSelectedRestFilter(null)}
                  >
                    All ({dishes.length})
                  </button>
                  {dishRestaurantNames.map(rName => (
                    <button 
                      key={rName}
                      className={`filter-chip ${selectedRestFilter === rName ? 'active' : ''}`}
                      onClick={() => setSelectedRestFilter(selectedRestFilter === rName ? null : rName)}
                    >
                      {rName}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Tab 1: Dishes Carousel */}
            {currentTab === 'dishes' && displayedDishes.length > 0 && (
              <div className="cards-carousel dishes-carousel">
                {displayedDishes.map((dish, idx) => (
                  <div 
                    key={dish.id || idx} 
                    className="dish-card"
                    onClick={() => {
                      setActiveModalItem(dish);
                      setModalType('dish');
                    }}
                  >
                    <div className="dish-card-image-wrap">
                      <img 
                        src={dish.imageUrl || FALLBACK_FOOD_IMG} 
                        alt={dish.name} 
                        className="dish-card-img"
                        onError={(e) => { 
                          e.target.onerror = null;
                          e.target.src = FALLBACK_FOOD_IMG;
                        }}
                      />
                      {dish.isBestseller && <span className="dish-bestseller-tag">⭐ Bestseller</span>}
                    </div>

                    <div className="dish-card-body">
                      <div className="dish-veg-row">
                        <div className={`veg-indicator ${dish.isVeg ? 'veg' : 'non-veg'}`}>
                          <span className="veg-dot"></span>
                        </div>
                        {dish.rating && (
                          <span className="dish-rating-badge">★ {dish.rating}</span>
                        )}
                      </div>

                      <h4 className="dish-title">{dish.name}</h4>
                      {dish.restaurantName && (
                        <span className="dish-rest-sub">{dish.restaurantName}</span>
                      )}

                      <div className="dish-bottom-row">
                        <span className="dish-price">₹{dish.price}</span>
                        <button 
                          className="dish-add-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (onAddToCart) {
                              onAddToCart(dish, dish.restaurantName);
                            } else {
                              onAction && onAction(`add 1 ${dish.name}`);
                            }
                          }}
                        >
                          <Plus size={14} />
                          <span>ADD</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Tab 2: Restaurants Carousel */}
            {currentTab === 'restaurants' && restaurants.length > 0 && (
              <div className="cards-carousel">
                {restaurants.map((rest, idx) => {
                  const cuisineStr = Array.isArray(rest.cuisines) 
                    ? rest.cuisines.slice(0, 3).join(', ') 
                    : (rest.cuisine || rest.category || 'Restaurant');
                  const rating = rest.avgRating || rest.rating || '4.2';
                  const dist = rest.distanceKm ? `${rest.distanceKm} km` : (rest.distance_km ? `${rest.distance_km} km` : '');
                  const cost = rest.costForTwo || rest.costForTwoMessage || rest.avg_cost_for_two || '';

                  return (
                    <div key={idx} className="entity-card" onClick={() => {
                      setActiveModalItem(rest);
                      setModalType(isDineoutServer ? 'dineout' : 'food');
                    }}>
                      <img 
                        src={rest.imageUrl || (isDineoutServer ? FALLBACK_REST_IMG : FALLBACK_FOOD_IMG)} 
                        alt={rest.name} 
                        className="card-image"
                        onError={(e) => { 
                          e.target.onerror = null;
                          e.target.src = isDineoutServer ? FALLBACK_REST_IMG : FALLBACK_FOOD_IMG;
                        }} 
                      />
                      {rest.offer && <div className="card-badge">{rest.offer}</div>}
                      <div className="card-title">{rest.name}</div>
                      <div className="card-subtitle">{cuisineStr}</div>
                      <div className="card-meta">
                        <span className="card-rating">★ {rating}</span>
                        {dist && <span>{dist}</span>}
                        {cost && <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{cost}</span>}
                      </div>

                      {/* Interactive Action Buttons on Card */}
                      <div className="card-actions-row">
                        {!isDineoutServer ? (
                          <>
                            <button 
                              className="card-btn primary orange"
                              onClick={(e) => {
                                e.stopPropagation();
                                onAction && onAction(`order from ${rest.name}`);
                              }}
                            >
                              <ShoppingBag size={13} /> Order Food
                            </button>
                            <button 
                              className="card-btn secondary"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (hasDishes) {
                                  setSelectedRestFilter(rest.name);
                                  setActiveTab('dishes');
                                } else {
                                  onAction && onAction(`show menu for ${rest.name}`);
                                }
                              }}
                            >
                              <Utensils size={13} /> {hasDishes ? 'View Dishes' : 'Menu'}
                            </button>
                          </>
                        ) : (
                          <button 
                            className="card-btn primary purple"
                            onClick={(e) => {
                              e.stopPropagation();
                              onAction && onAction(`book a table at ${rest.name} for 2 guests`);
                            }}
                          >
                            <Calendar size={13} /> Book Table
                          </button>
                        )}
                        <button 
                          className="card-btn icon-only"
                          title="View Details"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveModalItem(rest);
                            setModalType(isDineoutServer ? 'dineout' : 'food');
                          }}
                        >
                          <Info size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Tab 3: Instamart Products Carousel */}
            {currentTab === 'products' && products.length > 0 && (
              <div className="cards-carousel">
                {products.map((prod, idx) => (
                  <div key={idx} className="entity-card" onClick={() => {
                    setActiveModalItem(prod);
                    setModalType('product');
                  }}>
                      <img 
                        src={prod.imageUrl || FALLBACK_GROCERY_IMG} 
                        alt={prod.name} 
                        className="card-image"
                        onError={(e) => { 
                          e.target.onerror = null;
                          e.target.src = FALLBACK_GROCERY_IMG;
                        }} 
                      />
                    <div className="card-title" style={{ fontSize: '15px' }}>{prod.name}</div>
                    <div className="card-subtitle">{prod.brand || prod.category || prod.weight || 'Grocery'}</div>
                    <div className="card-meta">
                      <span style={{ fontSize: '16px', fontWeight: 800, color: '#16a34a' }}>
                        ₹{prod.price || prod.finalPrice || '0'}
                      </span>
                      {prod.quantity && <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{prod.quantity}</span>}
                    </div>

                    {/* Direct Add to Cart Button */}
                    <div className="card-actions-row">
                      <button 
                        className="card-btn primary green"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onAddToCart) {
                            onAddToCart({
                              id: prod.id || `im_${idx}`,
                              name: prod.name,
                              price: prod.price || prod.finalPrice || 0,
                              imageUrl: prod.imageUrl,
                              isVeg: true,
                              type: 'instamart'
                            }, 'Instamart Store');
                          } else {
                            onAction && onAction(`add 1 ${prod.name}`);
                          }
                        }}
                      >
                        <Plus size={14} /> Add to Cart
                      </button>
                      <button 
                        className="card-btn icon-only"
                        title="View Details"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveModalItem(prod);
                          setModalType('product');
                        }}
                      >
                        <Info size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {!isAgent && (
        <div style={{ marginLeft: '16px', marginTop: '12px' }}>
          <div style={{ backgroundColor: 'var(--border-color)', padding: '8px', borderRadius: '50%' }}>
            <User size={20} color="var(--text-secondary)" />
          </div>
        </div>
      )}

      {/* Item Detail Modal */}
      {activeModalItem && (
        <ItemDetailModal 
          item={activeModalItem} 
          type={modalType} 
          onClose={() => setActiveModalItem(null)} 
          onAction={onAction}
          onAddToCart={onAddToCart}
        />
      )}
    </div>
  );
}
```

### File: `frontend/src/App.css`
```css
.counter {
  font-size: 16px;
  padding: 5px 10px;
  border-radius: 5px;
  color: var(--accent);
  background: var(--accent-bg);
  border: 2px solid transparent;
  transition: border-color 0.3s;
  margin-bottom: 24px;

  &:hover {
    border-color: var(--accent-border);
  }
  &:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
}

.hero {
  position: relative;

  .base,
  .framework,
  .vite {
    inset-inline: 0;
    margin: 0 auto;
  }

  .base {
    width: 170px;
    position: relative;
    z-index: 0;
  }

  .framework,
  .vite {
    position: absolute;
  }

  .framework {
    z-index: 1;
    top: 34px;
    height: 28px;
    transform: perspective(2000px) rotateZ(300deg) rotateX(44deg) rotateY(39deg)
      scale(1.4);
  }

  .vite {
    z-index: 0;
    top: 107px;
    height: 26px;
    width: auto;
    transform: perspective(2000px) rotateZ(300deg) rotateX(40deg) rotateY(39deg)
      scale(0.8);
  }
}

#center {
  display: flex;
  flex-direction: column;
  gap: 25px;
  place-content: center;
  place-items: center;
  flex-grow: 1;

  @media (max-width: 1024px) {
    padding: 32px 20px 24px;
    gap: 18px;
  }
}

#next-steps {
  display: flex;
  border-top: 1px solid var(--border);
  text-align: left;

  & > div {
    flex: 1 1 0;
    padding: 32px;
    @media (max-width: 1024px) {
      padding: 24px 20px;
    }
  }

  .icon {
    margin-bottom: 16px;
    width: 22px;
    height: 22px;
  }

  @media (max-width: 1024px) {
    flex-direction: column;
    text-align: center;
  }
}

#docs {
  border-right: 1px solid var(--border);

  @media (max-width: 1024px) {
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}

.ticks {
  position: relative;
  width: 100%;

  &::before,
  &::after {
    content: '';
    position: absolute;
    top: -4.5px;
    border: 5px solid transparent;
    width: 0;
    height: 0;
  }

  &::before {
    left: 0;
    border-left-color: var(--border);
    border-top-color: var(--border);
  }

  &::after {
    right: 0;
    border-right-color: var(--border);
    border-top-color: var(--border);
  }
}

#spacer {
  height: 50px;
}
```

---

## 9. Complete Source Code — Design System & Global Stylesheet

### File: `frontend/src/index.css`
```css
:root {
  /* Liquid Glass Theme: Vibrant Background for maximum glass contrast */
  --bg-gradient: linear-gradient(135deg, #fc8019 0%, #ffb347 40%, #ffcc80 70%, #ffffff 100%);
  
  /* Extreme Glass Surfaces */
  --panel-bg: rgba(255, 255, 255, 0.25);
  --surface-bg: rgba(255, 255, 255, 0.15);
  --border-color: rgba(255, 255, 255, 0.4);
  
  /* Text */
  --text-primary: #1f2937;
  --text-secondary: #4b5563;
  
  /* Swiggy Accents */
  --orange-primary: #fc8019;
  --orange-hover: #e57316;
  --orange-glow: rgba(252, 128, 25, 0.4);
  
  /* Status Colors */
  --status-success: #16a34a;
  --status-warning: #ca8a04;
  --status-error: #dc2626;

  /* Liquid Glass Specifics */
  --glass-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
  --glass-inset: inset 0 1px 2px rgba(255, 255, 255, 0.8), inset 0 -1px 2px rgba(0, 0, 0, 0.05);
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: system-ui, -apple-system, sans-serif;
  background: var(--bg-gradient);
  background-attachment: fixed;
  color: var(--text-primary);
  line-height: 1.5;
  height: 100vh;
  overflow: hidden;
}

#root {
  height: 100%;
}

/* Background Animated Blobs for Glass Refraction */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: relative;
  z-index: 1;
  overflow: hidden;
}

.app-container::before, .app-container::after {
  content: "";
  position: absolute;
  border-radius: 50%;
  z-index: -1;
  filter: blur(80px);
}

.app-container::before {
  top: -10%; left: -10%;
  width: 400px; height: 400px;
  background: rgba(255, 255, 255, 0.8);
}

.app-container::after {
  bottom: -10%; right: -10%;
  width: 500px; height: 500px;
  background: rgba(252, 128, 25, 0.6);
}

/* Header / Status Panel */
.header-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--panel-bg);
  border-bottom: 1px solid var(--border-color);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  box-shadow: var(--glass-shadow);
  z-index: 10;
}

.brand-title {
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.2);
  font-weight: 800;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.location-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--border-color);
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.8), 0 2px 5px rgba(0,0,0,0.04);
}

.mcp-status-group {
  display: flex;
  gap: 20px;
}

.mcp-status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
  font-weight: 600;
  text-shadow: 0 1px 1px rgba(255,255,255,0.5);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.8);
}

.status-dot.connected { background-color: var(--status-success); box-shadow: 0 0 8px var(--status-success); }
.status-dot.degraded { background-color: var(--status-warning); box-shadow: 0 0 8px var(--status-warning); }
.status-dot.disconnected { background-color: var(--status-error); box-shadow: 0 0 8px var(--status-error); }

/* Main Chat Area */
.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  position: relative;
}

.messages-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Message Bubbles */
.message-row {
  display: flex;
  width: 100%;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.agent {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 85%;
  padding: 16px 20px;
  border-radius: 20px;
  font-size: 15px;
}

.message-row.user .message-bubble {
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-color);
  box-shadow: var(--glass-shadow), var(--glass-inset);
  color: var(--text-primary);
  font-weight: 500;
  border-bottom-right-radius: 6px;
}

.message-row.agent .message-bubble {
  background-color: transparent;
  color: var(--text-primary);
  width: 100%;
  padding: 0;
}

.agent-text-content {
  margin-top: 12px;
  font-size: 16px;
  line-height: 1.6;
  padding: 16px;
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  box-shadow: var(--glass-shadow), var(--glass-inset);
}

/* Control Plane / Orchestration Timeline */
.control-plane-card {
  background: var(--surface-bg);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 20px;
  margin-bottom: 20px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  box-shadow: var(--glass-shadow), var(--glass-inset);
}

.control-plane-header {
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
  font-weight: 800;
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.timeline-step {
  display: flex;
  margin-bottom: 10px;
  color: #374151;
  font-weight: 500;
}

.timeline-step.active {
  color: #111827;
}

.timeline-step.success {
  color: var(--status-success);
}

.timeline-label {
  width: 140px;
  flex-shrink: 0;
  font-weight: 700;
}

.timeline-value {
  flex: 1;
  word-break: break-word;
}

/* Routing Visualization */
.routing-container {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.4);
}

.routing-server-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.3);
  border: 1px solid transparent;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.5);
}

.routing-server-row.selected {
  background: rgba(252, 128, 25, 0.2);
  color: #9a3412;
  font-weight: 800;
  border-color: rgba(252, 128, 25, 0.5);
  box-shadow: 0 4px 12px rgba(252, 128, 25, 0.15), inset 0 1px 1px rgba(255,255,255,0.8);
}

.routing-reasoning {
  margin-top: 12px;
  padding-left: 14px;
  border-left: 3px solid var(--orange-primary);
  color: #1f2937;
  font-size: 13px;
  font-weight: 500;
}

/* Loading Indicator */
.activity-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.2);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 14px;
  padding: 12px 0;
  font-weight: 700;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 3px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Input Area */
.input-container {
  padding: 24px;
  background: rgba(255, 255, 255, 0.3);
  border-top: 1px solid var(--border-color);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.05);
}

.input-box {
  display: flex;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--border-color);
  border-radius: 30px;
  padding: 8px 16px;
  align-items: center;
  box-shadow: var(--glass-inset), 0 8px 24px rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(10px);
}

.input-box:focus-within {
  border-color: rgba(252, 128, 25, 0.5);
  box-shadow: 0 0 0 3px rgba(252, 128, 25, 0.2), var(--glass-inset);
  background: rgba(255, 255, 255, 0.8);
}

.chat-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 16px;
  padding: 12px;
  outline: none;
  font-weight: 500;
}

.chat-input::placeholder {
  color: #6b7280;
}

.send-button {
  background: linear-gradient(135deg, #fc8019 0%, #ea580c 100%);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 50%;
  width: 44px;
  height: 44px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(252, 128, 25, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.5);
}

.send-button:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 6px 16px rgba(252, 128, 25, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.6);
}

.send-button:disabled {
  background: rgba(156, 163, 175, 0.5);
  box-shadow: none;
  cursor: not-allowed;
  border-color: transparent;
}

/* Rich Restaurant/Product Cards */
.cards-carousel {
  display: flex;
  overflow-x: auto;
  gap: 20px;
  padding-bottom: 24px;
  margin-top: 20px;
  scrollbar-width: none;
}

.cards-carousel::-webkit-scrollbar {
  display: none;
}

.entity-card {
  flex: 0 0 280px;
  background: rgba(255, 255, 255, 0.35);
  border: 1px solid var(--border-color);
  border-radius: 24px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  box-shadow: var(--glass-shadow), var(--glass-inset);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.entity-card:hover {
  transform: translateY(-6px);
  background: rgba(255, 255, 255, 0.45);
  box-shadow: 0 12px 40px rgba(31, 38, 135, 0.2), var(--glass-inset);
}

.card-image {
  width: 100%;
  height: 130px;
  object-fit: cover;
  border-radius: 14px;
  background-color: #f1f5f9;
}

.card-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 800;
  color: #ea580c;
  background: rgba(255, 255, 255, 0.8);
  padding: 4px 8px;
  border-radius: 6px;
  width: fit-content;
}

.card-title {
  font-weight: 800;
  font-size: 16px;
  color: var(--text-primary);
}

.card-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  font-weight: 600;
}

.card-rating {
  color: #b45309;
  background-color: #fef3c7;
  padding: 2px 6px;
  border-radius: 4px;
}

.card-action {
  margin-top: auto;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px;
  border-radius: 12px;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: inset 0 1px 2px rgba(255,255,255,1), 0 4px 6px rgba(0,0,0,0.05);
}

.card-action:hover {
  background: rgba(255, 255, 255, 0.8);
  transform: scale(1.02);
}

/* Utilities */
.text-orange { color: #ea580c; font-weight: 800; }

/* Markdown Styles inside agent text */
.agent-text-content p { margin-bottom: 12px; }
.agent-text-content strong { color: #c2410c; font-weight: 700; }
.agent-text-content ul { padding-left: 20px; margin-bottom: 12px; }
.agent-text-content li { margin-bottom: 6px; }

/* Mobile Responsive Adjustments */
@media (max-width: 768px) {
  .header-panel {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    padding: 12px 16px;
    justify-content: center;
  }
  
  .brand-title {
    font-size: 11px;
    width: 100%;
    justify-content: center;
  }

  .mcp-status-group {
    width: 100%;
    justify-content: center;
    font-size: 11px;
    gap: 16px;
  }

  .messages-list {
    padding: 12px;
  }

  .message-bubble {
    max-width: 100%;
    padding: 12px 16px;
  }
  
  .agent-text-content {
    font-size: 14px;
    padding: 12px;
  }

  .control-plane-card {
    font-size: 11px;
    padding: 12px;
  }

  .timeline-step {
    flex-direction: column;
    margin-bottom: 12px;
  }

  .timeline-label {
    width: 100%;
    margin-bottom: 4px;
    color: var(--text-primary);
  }

  .input-container {
    padding: 12px;
  }
  
  .input-box {
    padding: 4px 12px;
  }
  
  .chat-input {
    font-size: 14px;
    padding: 8px;
  }

  .entity-card {
    flex: 0 0 85vw;
  }
}

/* Interactive Card Action Buttons */
.card-actions-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.4);
}

.card-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
  text-decoration: none;
}

.card-btn.primary.orange {
  background: linear-gradient(135deg, #fc8019 0%, #ea580c 100%);
  color: white;
  flex: 1;
  box-shadow: 0 4px 12px rgba(234, 88, 12, 0.25);
}

.card-btn.primary.orange:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(234, 88, 12, 0.35);
  background: linear-gradient(135deg, #fb923c 0%, #c2410c 100%);
}

.card-btn.primary.green {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
  flex: 1;
  box-shadow: 0 4px 12px rgba(22, 163, 74, 0.25);
}

.card-btn.primary.green:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(22, 163, 74, 0.35);
  background: linear-gradient(135deg, #4ade80 0%, #15803d 100%);
}

.card-btn.primary.purple {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  color: white;
  flex: 1;
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.25);
}

.card-btn.primary.purple:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(124, 58, 237, 0.35);
}

.card-btn.secondary {
  background: rgba(255, 255, 255, 0.65);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
}

.card-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.95);
  transform: translateY(-1px);
}

.card-btn.icon-only {
  padding: 8px;
  background: rgba(255, 255, 255, 0.65);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.card-btn.icon-only:hover {
  background: rgba(255, 255, 255, 0.95);
  color: var(--text-primary);
  transform: translateY(-1px);
}

/* Confirmation Quick Action Bar */
.quick-actions-bar {
  display: flex;
  gap: 12px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
}

.quick-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
  border: none;
}

.quick-action-btn.confirm {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
  box-shadow: 0 4px 14px rgba(22, 163, 74, 0.3);
}

.quick-action-btn.confirm:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(22, 163, 74, 0.4);
}

.quick-action-btn.cancel {
  background: rgba(255, 255, 255, 0.7);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.quick-action-btn.cancel:hover {
  background: #fef2f2;
  border-color: #ef4444;
  transform: translateY(-1px);
}

/* Item Detail Modal */
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: fadeIn 0.2s ease-out;
}

.modal-container {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 24px;
  width: 100%;
  max-width: 540px;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.25);
  position: relative;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(30px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.modal-close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  transition: all 0.2s;
}

.modal-close-btn:hover {
  background: rgba(0, 0, 0, 0.75);
  transform: scale(1.08);
}

.modal-image-container {
  position: relative;
  width: 100%;
  height: 220px;
  overflow: hidden;
  background: #f1f5f9;
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
}

.modal-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.modal-badge {
  position: absolute;
  bottom: 14px;
  left: 14px;
  background: rgba(234, 88, 12, 0.95);
  color: white;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.modal-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.modal-title {
  font-size: 20px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.25;
  margin-bottom: 4px;
}

.modal-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}

.modal-rating {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #b45309;
  background-color: #fef3c7;
  padding: 5px 10px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 800;
  flex-shrink: 0;
}

.modal-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.04);
  padding: 4px 10px;
  border-radius: 8px;
}

.meta-pill.certified {
  color: #15803d;
  background: #dcfce7;
}

.modal-pricing-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 14px 18px;
  border-radius: 14px;
}

.pricing-info {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.current-price {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
}

.mrp-price {
  font-size: 14px;
  color: #94a3b8;
  text-decoration: line-through;
}

.discount-tag {
  font-size: 11px;
  font-weight: 800;
  color: #15803d;
  background: #dcfce7;
  padding: 2px 6px;
  border-radius: 4px;
}

.stock-status {
  font-size: 12px;
  font-weight: 700;
}

.stock-status.in-stock {
  color: #15803d;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.popular-items-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.popular-item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 10px;
  font-size: 13px;
  color: var(--text-primary);
}

.add-dish-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #ffffff;
  color: #ea580c;
  border: 1px solid #fed7aa;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}

.add-dish-btn:hover {
  background: #ea580c;
  color: white;
  border-color: #ea580c;
}

.modal-footer {
  margin-top: 8px;
}

.btn-group {
  display: flex;
  gap: 12px;
}

.modal-primary-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 20px;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 800;
  border: none;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.modal-primary-btn.green {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
  box-shadow: 0 6px 20px rgba(22, 163, 74, 0.35);
}

.modal-primary-btn.green:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(22, 163, 74, 0.45);
}

.modal-primary-btn.orange {
  background: linear-gradient(135deg, #fc8019 0%, #ea580c 100%);
  color: white;
  box-shadow: 0 6px 20px rgba(234, 88, 12, 0.35);
}

.modal-primary-btn.orange:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(234, 88, 12, 0.45);
}

.modal-primary-btn.purple {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  color: white;
  box-shadow: 0 6px 20px rgba(124, 58, 237, 0.35);
}

.modal-primary-btn.purple:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(124, 58, 237, 0.45);
}

.modal-secondary-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px 18px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 700;
  background: #f1f5f9;
  color: var(--text-primary);
  border: 1px solid #cbd5e1;
  cursor: pointer;
  transition: all 0.15s;
}

.modal-secondary-btn:hover {
  background: #e2e8f0;
}

/* Location Pill & Interactive Styles */
.location-pill-interactive {
  cursor: pointer;
  border: 1px solid rgba(234, 88, 12, 0.3);
  transition: all 0.2s ease;
}

.location-pill-interactive:hover {
  background: rgba(255, 255, 255, 0.95);
  border-color: #ea580c;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(234, 88, 12, 0.15);
}

.location-pill-text {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.location-change-tag {
  font-size: 10px;
  color: #ea580c;
  background: rgba(234, 88, 12, 0.1);
  padding: 1px 6px;
  border-radius: 10px;
  margin-left: 2px;
  font-weight: 700;
  text-transform: uppercase;
}

.live-dot {
  width: 8px;
  height: 8px;
  background: #10b981;
  border-radius: 50%;
  display: inline-block;
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
  animation: liveGpsPulse 1.8s infinite;
}

@keyframes liveGpsPulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
  70% { transform: scale(1.1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

/* Location Selector Modal */
.location-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
  animation: modalFadeIn 0.2s ease-out;
}

.location-modal-card {
  background: #ffffff;
  border-radius: 20px;
  width: 100%;
  max-width: 480px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(0, 0, 0, 0.05);
  animation: modalSlideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.location-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px;
  border-bottom: 1px solid #f1f5f9;
}

.location-modal-body {
  padding: 20px 22px;
  overflow-y: auto;
}

.live-detect-action-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #f0fdf4;
  border: 1.5px solid #86efac;
  color: #166534;
  cursor: pointer;
  transition: all 0.15s ease;
}

.live-detect-action-btn:hover:not(:disabled) {
  background: #dcfce7;
  border-color: #4ade80;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15);
}

.live-detect-icon-wrapper {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #22c55e;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.live-badge {
  font-size: 9px;
  background: #16a34a;
  color: white;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 800;
  letter-spacing: 0.5px;
}

.location-search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 10px 14px;
  transition: border-color 0.15s;
}

.location-search-box:focus-within {
  border-color: #ea580c;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(234, 88, 12, 0.1);
}

.location-search-input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  width: 100%;
  color: var(--text-primary);
}

.location-search-results {
  margin-top: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08);
}

.location-search-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.1s;
}

.location-search-item:last-child {
  border-bottom: none;
}

.location-search-item:hover {
  background: #f8fafc;
}

.saved-addresses-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

.saved-address-card {
  position: relative;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1.5px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.15s ease;
}

.saved-address-card:hover {
  border-color: #cbd5e1;
  background: #ffffff;
}

.saved-address-card.selected {
  border-color: #ea580c;
  background: #fff7ed;
}

.address-category-tag {
  font-size: 10px;
  font-weight: 800;
  color: #ea580c;
  background: rgba(234, 88, 12, 0.12);
  padding: 2px 6px;
  border-radius: 6px;
  text-transform: uppercase;
}

.selected-indicator {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #ea580c;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Header Navigation & Actions */
.header-actions-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--border-color);
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.8), 0 2px 5px rgba(0,0,0,0.04);
}

.header-action-btn:hover {
  background: rgba(255, 255, 255, 0.95);
  transform: translateY(-1px);
  border-color: #ea580c;
}

.header-cart-badge {
  background: #ea580c;
  color: white;
  font-size: 10px;
  font-weight: 800;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 2px;
}

.cart-header-btn.has-items {
  border-color: #ea580c;
  color: #ea580c;
  background: #fff7ed;
}

/* Unified Card Deck */
.unified-card-deck {
  margin-top: 14px;
}

.deck-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.deck-tabs-pills {
  display: flex;
  align-items: center;
  gap: 8px;
}

.deck-tab-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.deck-tab-pill.active {
  background: #ea580c;
  color: #ffffff;
  border-color: #ea580c;
  box-shadow: 0 2px 8px rgba(234, 88, 12, 0.3);
}

.deck-subtitle-hint {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}

.deck-filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  overflow-x: auto;
}

.deck-filter-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
}

.deck-filter-chips {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-chip {
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid #e5e7eb;
  padding: 3px 9px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.filter-chip.active {
  background: #ea580c;
  color: #ffffff;
  border-color: #ea580c;
}

/* Dishes Carousel & Card */
.dishes-carousel {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 4px 2px 14px 2px;
  scrollbar-width: thin;
}

.dish-card {
  flex: 0 0 210px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(12px);
}

.dish-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 22px rgba(234, 88, 12, 0.15);
  border-color: rgba(234, 88, 12, 0.3);
}

.dish-card-image-wrap {
  position: relative;
  width: 100%;
  height: 120px;
  background: #f3f4f6;
  overflow: hidden;
}

.dish-card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.dish-card:hover .dish-card-img {
  transform: scale(1.04);
}

.dish-bestseller-tag {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(17, 24, 39, 0.85);
  color: #fde047;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
  backdrop-filter: blur(4px);
}

.dish-card-body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.dish-veg-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.veg-indicator {
  width: 14px;
  height: 14px;
  border: 1.5px solid #16a34a;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1px;
}

.veg-indicator .veg-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #16a34a;
}

.veg-indicator.non-veg {
  border-color: #b91c1c;
}

.veg-indicator.non-veg .veg-dot {
  background: #b91c1c;
  clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
  border-radius: 0;
}

.dish-rating-badge {
  font-size: 11px;
  font-weight: 700;
  color: #15803d;
  background: #dcfce7;
  padding: 1px 6px;
  border-radius: 4px;
}

.dish-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.35;
}

.dish-rest-sub {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dish-bottom-row {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 6px;
}

.dish-price {
  font-size: 15px;
  font-weight: 800;
  color: var(--text-primary);
}

.dish-add-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  background: #ffffff;
  border: 1.5px solid #16a34a;
  color: #16a34a;
  font-size: 12px;
  font-weight: 800;
  padding: 4px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 3px rgba(22, 163, 74, 0.15);
}

.dish-add-btn:hover {
  background: #16a34a;
  color: #ffffff;
  box-shadow: 0 3px 8px rgba(22, 163, 74, 0.3);
  transform: scale(1.05);
}

/* Floating Bottom Cart Bar */
.floating-cart-wrapper {
  position: fixed;
  bottom: 84px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  padding: 0 16px;
  z-index: 50;
  pointer-events: none;
  animation: slideUpBounce 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slideUpBounce {
  from { transform: translateY(50px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.floating-cart-bar {
  pointer-events: auto;
  width: 100%;
  max-width: 620px;
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  color: #ffffff;
  padding: 10px 18px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 10px 25px -3px rgba(22, 163, 74, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.floating-cart-bar:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 30px -3px rgba(22, 163, 74, 0.5);
}

.cart-bar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cart-icon-bubble {
  position: relative;
  background: rgba(255, 255, 255, 0.2);
  padding: 7px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cart-badge-count {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ffffff;
  color: #16a34a;
  font-size: 10px;
  font-weight: 800;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.cart-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.cart-count-text {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.cart-dot-divider {
  opacity: 0.6;
}

.cart-amount-text {
  font-size: 15px;
  font-weight: 800;
}

.cart-restaurant-name {
  font-size: 11px;
  opacity: 0.85;
  margin-left: 4px;
}

.cart-view-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.4);
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cart-view-btn:hover {
  background: #ffffff;
  color: #16a34a;
}

/* Cart Drawer */
.cart-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(6px);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
  animation: fadeIn 0.2s ease;
}

.cart-drawer {
  width: 100%;
  max-width: 440px;
  height: 100%;
  background: #ffffff;
  box-shadow: -10px 0 30px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.cart-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
}

.cart-header-title-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cart-header-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: rgba(252, 128, 25, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
}

.cart-header-icon.orange {
  background: rgba(234, 88, 12, 0.12);
}

.cart-drawer-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0;
}

.cart-restaurant-sub {
  font-size: 12px;
  color: var(--text-secondary);
}

.cart-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cart-delivery-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  color: #9a3412;
}

.cart-items-scroll {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 8px;
}

.cart-item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed #e5e7eb;
}

.cart-item-details {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.cart-item-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.3;
}

.cart-item-unit-price {
  font-size: 11px;
  color: var(--text-secondary);
}

.cart-qty-stepper {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1.5px solid #16a34a;
  border-radius: 8px;
  padding: 3px 8px;
  background: #ffffff;
}

.qty-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #16a34a;
  padding: 2px;
}

.qty-number {
  font-size: 13px;
  font-weight: 800;
  color: #16a34a;
  min-width: 14px;
  text-align: center;
}

.cart-item-total {
  font-size: 13px;
  font-weight: 800;
  color: var(--text-primary);
  min-width: 55px;
  text-align: right;
}

.cart-coupon-section {
  background: #f9fafb;
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  padding: 12px;
}

.coupon-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.coupon-input {
  flex: 1;
  border: 1px solid #e5e7eb;
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 700;
  outline: none;
}

.coupon-apply-btn {
  background: #ea580c;
  color: #ffffff;
  border: none;
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.2s ease;
}

.coupon-apply-btn:hover {
  background: #c2410c;
}

.coupon-msg {
  font-size: 11px;
  font-weight: 600;
  margin-top: 6px;
}

.coupon-msg.success { color: #16a34a; }
.coupon-msg.error { color: #dc2626; }

.active-coupon-tag {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #dcfce7;
  color: #15803d;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  margin-top: 8px;
}

.remove-coupon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: #15803d;
  display: flex;
  align-items: center;
}

.cart-bill-section {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
}

.bill-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.bill-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.bill-row.discount {
  color: #16a34a;
  font-weight: 700;
}

.free-tag {
  color: #16a34a;
  font-weight: 800;
}

.bill-divider {
  height: 1px;
  background: #e5e7eb;
  margin: 10px 0;
}

.bill-row.total {
  font-size: 14px;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 0;
}

.final-total {
  font-size: 17px;
  color: #ea580c;
}

.cart-assurance {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  color: #16a34a;
  background: #f0fdf4;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #bbf7d0;
}

.cart-drawer-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid #e5e7eb;
}

.cart-clear-btn {
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  color: var(--text-secondary);
  padding: 11px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cart-clear-btn:hover {
  background: #fee2e2;
  color: #b91c1c;
}

.cart-checkout-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%);
  color: #ffffff;
  border: none;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(234, 88, 12, 0.3);
  transition: all 0.2s ease;
}

.cart-checkout-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(234, 88, 12, 0.4);
}

.cart-checkout-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.empty-cart-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.empty-icon-wrap {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-cart-state h3 {
  font-size: 16px;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-cart-state p {
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 240px;
  line-height: 1.5;
  margin-bottom: 20px;
}

.cart-browse-btn {
  background: #ea580c;
  color: #ffffff;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.cart-success-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 20px;
  text-align: center;
}

.success-icon-bubble {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: #dcfce7;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.success-title {
  font-size: 18px;
  font-weight: 800;
  color: #15803d;
  margin-bottom: 6px;
}

.success-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 24px;
  line-height: 1.5;
}

.order-summary-card {
  width: 100%;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 24px;
}

.order-summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px dashed #e5e7eb;
}

.order-summary-row:last-child {
  border-bottom: none;
}

.order-code {
  font-family: monospace;
  font-weight: 700;
  color: #ea580c;
}

.order-total-val {
  font-weight: 800;
  color: var(--text-primary);
}

.order-eta-val {
  font-weight: 800;
  color: #16a34a;
}

.success-actions {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Orders Drawer */
.orders-scroll-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.live-tracking-card {
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border: 1.5px solid #fdba74;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 4px 14px rgba(234, 88, 12, 0.1);
}

.tracking-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.live-pulse-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #ea580c;
  color: #ffffff;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: 9999px;
  margin-bottom: 4px;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ffffff;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
  100% { opacity: 1; transform: scale(1); }
}

.tracking-order-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0;
}

.tracking-eta-box {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #ffffff;
  border: 1px solid #fed7aa;
  padding: 4px 10px;
  border-radius: 20px;
}

.eta-text {
  font-size: 12px;
  font-weight: 800;
  color: #ea580c;
}

.tracking-stepper {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  position: relative;
  margin: 20px 0;
}

.tracking-stepper::before {
  content: '';
  position: absolute;
  top: 14px;
  left: 20px;
  right: 20px;
  height: 2px;
  background: #e5e7eb;
  z-index: 1;
}

.step-item {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  width: 72px;
}

.step-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #e5e7eb;
  color: #9ca3af;
  font-size: 11px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 6px;
  transition: all 0.2s ease;
}

.step-item.completed .step-circle {
  background: #16a34a;
  color: #ffffff;
  border-color: #16a34a;
}

.step-item.current .step-circle {
  background: #ea580c;
  color: #ffffff;
  border-color: #ea580c;
  box-shadow: 0 0 0 3px rgba(234, 88, 12, 0.25);
  animation: pulse 2s infinite;
}

.step-label {
  font-size: 10px;
  font-weight: 700;
  color: #6b7280;
  line-height: 1.2;
}

.step-item.completed .step-label,
.step-item.current .step-label {
  color: var(--text-primary);
}

.rider-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #ffffff;
  border-radius: 10px;
  padding: 10px 12px;
  border: 1px solid #fed7aa;
}

.rider-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #ea580c;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rider-info {
  flex: 1;
}

.rider-name {
  font-size: 13px;
  font-weight: 800;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.rider-rating {
  font-size: 11px;
  font-weight: 700;
  color: #15803d;
  background: #dcfce7;
  padding: 1px 5px;
  border-radius: 4px;
}

.rider-vehicle {
  font-size: 11px;
  color: var(--text-secondary);
}

.rider-call-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #dcfce7;
  color: #15803d;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  transition: all 0.2s ease;
}

.rider-call-btn:hover {
  background: #16a34a;
  color: #ffffff;
}

.orders-section-heading {
  font-size: 13px;
  font-weight: 800;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.past-order-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.past-order-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
}

.past-order-merchant {
  font-size: 14px;
  font-weight: 800;
  color: var(--text-primary);
  display: block;
}

.past-order-time {
  font-size: 11px;
  color: var(--text-secondary);
}

.order-status-pill {
  font-size: 10px;
  font-weight: 800;
  color: #16a34a;
  background: #dcfce7;
  padding: 2px 7px;
  border-radius: 6px;
  text-transform: uppercase;
}

.past-order-items {
  padding: 8px 0;
  border-top: 1px dashed #f3f4f6;
  border-bottom: 1px dashed #f3f4f6;
  margin-bottom: 10px;
}

.past-item-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.past-order-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.past-order-total {
  display: flex;
  flex-direction: column;
}

.past-order-total span {
  font-size: 10px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.past-order-total strong {
  font-size: 14px;
  color: var(--text-primary);
}

.reorder-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #ea580c;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.reorder-btn:hover {
  background: #ea580c;
  color: #ffffff;
}
```

---

## 10. Operational Guidelines for AI Agents

1. **Maintain Relative Paths**: Never hardcode origin URLs (like `http://localhost:8000`). All `fetch` calls must use relative endpoints (`/chat`, `/cart`, `/cart/add`, etc.) to support both Vite dev and unified FastAPI production deployment on Render.
2. **Preserve State Isolation**: When adding items to the cart, always pass `activeLocation?.addressId` to maintain location parity across food menus and checkout calculations.
3. **Single-Restaurant Cart Enforcement**: Swiggy's backend will reject or flush carts that mix multiple food restaurants. The frontend gracefully informs users of single-restaurant constraints.
4. **Image CDN Resilience**: Always preserve `onError` handlers with fallbacks (`FALLBACK_FOOD_IMG`, `FALLBACK_REST_IMG`, `FALLBACK_GROCERY_IMG`) to handle flaky CDN URLs or expired asset paths from third-party catalogs.
5. **Two-Way Sync**: Cart actions (`add`, `update`, `clear`, `coupon`) mutate the in-memory `session_cart` on FastAPI and simultaneously trigger background MCP tool calls (`food:update_food_cart`, `instamart:update_cart`) to ensure database and session state are always in harmony.



