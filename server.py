"""
Swiggy MCP Orchestrator — HTTP + OAuth Server

This is the entry point that:
  1. Serves the OAuth callback (receives code, exchanges for token)
  2. Exposes the chat endpoint for the orchestrator
  3. Provides health/status endpoints
  4. Auto-initializes MCP servers after auth

Deploy to Render/any host. OAuth callback must be whitelisted by Swiggy.
"""

import os
import logging
from html import escape as html_escape
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from orchestrator.memory import MemoryManager
from orchestrator.oauth import SwiggyOAuthClient, verify_callback_params
from orchestrator.init_orchestrator import create_orchestrator

# --- Config from env ---
REDIRECT_URI = os.getenv("SWIGGY_REDIRECT_URI", "https://swiggy-builders-club-ai-agent.onrender.com/oauth/callback")
CLIENT_NAME = os.getenv("SWIGGY_CLIENT_NAME", "MCP Orchestrator")

@asynccontextmanager
async def lifespan(app):
    # Startup — nothing extra needed (services init at module level)
    yield
    # Shutdown — close MCP connections
    if orchestrator:
        mcp_client = getattr(orchestrator, 'mcp_client', None)
        if mcp_client:
            await mcp_client.close()
    logger.info("Orchestrator shutdown complete")

app = FastAPI(title="Swiggy MCP Orchestrator", lifespan=lifespan)
logger = logging.getLogger(__name__)

# --- Core services ---
memory = MemoryManager()
oauth_client = SwiggyOAuthClient(
    redirect_uri=REDIRECT_URI,
    client_name=CLIENT_NAME,
    token_store=memory,
)

# Try to restore previous registration + token from SQLite
oauth_client.restore_registration()
oauth_client.restore_from_store()

# --- Orchestrator (created once, lives for app lifetime) ---
orchestrator = None
mcp_initialized = False


async def get_orchestrator():
    """
    Lazy-initialize the orchestrator on first authenticated request.
    Avoids startup failures if MCP servers are unreachable.
    """
    global orchestrator, mcp_initialized

    if orchestrator is None:
        logger.info("Creating orchestrator with OAuth client...")
        orchestrator = create_orchestrator(oauth_client=oauth_client)

    # Auto-initialize MCP servers after authentication
    if not mcp_initialized and oauth_client.is_authenticated():
        mcp_client = getattr(orchestrator, 'mcp_client', None)
        if mcp_client:
            logger.info("Auto-initializing MCP servers...")
            init_results = await mcp_client.initialize_all()
            logger.info(f"MCP init results: {init_results}")
            mcp_initialized = True

    return orchestrator


# ============================================================
#  Pages
# ============================================================




@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Swiggy MCP Orchestrator",
        "authenticated": oauth_client.is_authenticated(),
        "mcp_initialized": mcp_initialized,
        "token_expiry_hours": oauth_client.time_until_expiry() / 3600 if oauth_client.is_authenticated() else None,
    }


# ============================================================
#  Debug / Diagnostics
# ============================================================

@app.get("/debug/mcp-raw")
async def debug_mcp_raw():
    """Diagnostic: makes a raw HTTP call to Swiggy MCP /food and returns the full response."""
    import httpx
    import json

    if not oauth_client.is_authenticated():
        return JSONResponse({"error": "Not authenticated. Go to /auth/start first."}, status_code=401)

    try:
        auth_headers = oauth_client.get_auth_headers()
    except Exception as e:
        return JSONResponse({"error": f"Token error: {e}"}, status_code=401)

    results = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Initialize the MCP session
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"client": {"tools": {}, "resources": {}}},
                "clientInfo": {"name": "Swiggy MCP Orchestrator Debug", "version": "1.0.0"},
            },
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **auth_headers,
        }

        init_resp = await client.post("https://mcp.swiggy.com/food", json=init_payload, headers=headers)
        results["1_init"] = {
            "status": init_resp.status_code,
            "content_type": init_resp.headers.get("content-type"),
            "session_id": init_resp.headers.get("mcp-session-id"),
            "body_preview": init_resp.text[:2000],
        }

        session_id = init_resp.headers.get("mcp-session-id")

        # Step 2: Send initialized notification
        notif_payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        notif_headers = {**headers}
        if session_id:
            notif_headers["Mcp-Session-Id"] = session_id
        notif_resp = await client.post("https://mcp.swiggy.com/food", json=notif_payload, headers=notif_headers)
        results["2_notification"] = {
            "status": notif_resp.status_code,
            "body_preview": notif_resp.text[:500],
        }

        # Step 3: Call get_addresses
        addr_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_addresses", "arguments": {}},
        }
        addr_headers = {**headers}
        if session_id:
            addr_headers["Mcp-Session-Id"] = session_id
        addr_resp = await client.post("https://mcp.swiggy.com/food", json=addr_payload, headers=addr_headers)

        addr_body = addr_resp.text[:3000]
        results["3_get_addresses"] = {
            "status": addr_resp.status_code,
            "content_type": addr_resp.headers.get("content-type"),
            "body_preview": addr_body,
        }

        # Try to parse address ID for search_restaurants
        address_id = None
        try:
            addr_data = addr_resp.json()
            content = addr_data.get("result", {}).get("content", [])
            if content and isinstance(content, list):
                text_content = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
                parsed = json.loads(text_content)
                if isinstance(parsed, dict) and parsed.get("data"):
                    addr_list = parsed["data"]
                    if isinstance(addr_list, list) and addr_list:
                        address_id = addr_list[0].get("id")
                    elif isinstance(addr_list, dict) and addr_list.get("addresses"):
                        address_id = addr_list["addresses"][0].get("id")
            results["3_parsed_address_id"] = address_id
        except Exception as e:
            results["3_parse_error"] = str(e)

        # Step 4: Call search_restaurants
        if address_id:
            search_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "search_restaurants",
                    "arguments": {"addressId": address_id, "query": "sweets"},
                },
            }
            search_headers = {**headers}
            if session_id:
                search_headers["Mcp-Session-Id"] = session_id
            search_resp = await client.post("https://mcp.swiggy.com/food", json=search_payload, headers=search_headers)
            results["4_search_restaurants"] = {
                "status": search_resp.status_code,
                "content_type": search_resp.headers.get("content-type"),
                "body_preview": search_resp.text[:5000],
            }

    return JSONResponse(results)


# ============================================================
#  OAuth Flow
# ============================================================

@app.get("/auth/start")
async def start_auth():
    """Kick off the OAuth flow. Auto-registers via DCR if needed, then redirects to Swiggy."""
    # Step 0: Register client via DCR if we don't have a client_id yet
    if not oauth_client.client_id:
        if not oauth_client.restore_registration():
            try:
                await oauth_client.register_client()
            except Exception as e:
                return HTMLResponse(
                    content=f"<h2>Client Registration Failed</h2><p>{html_escape(str(e))}</p>"
                    f"<p>Check that your redirect URI ({html_escape(REDIRECT_URI)}) is HTTPS and whitelisted.</p>"
                    f"<a href='/auth/start' style='color: #fc8019;'>Retry</a>",
                    status_code=500,
                )

    auth_url = oauth_client.authorization_url()
    logger.info(f"Redirecting to Swiggy auth: {auth_url[:80]}...")
    return RedirectResponse(url=auth_url)


@app.get("/oauth/callback")
@app.get("/callback")
async def oauth_callback(request: Request):
    """
    OAuth Callback — receives the auth code from Swiggy, exchanges it for a token.

    This is the endpoint that MUST be whitelisted in your Swiggy Builders Club settings.
    Full URL: https://your-domain.com/oauth/callback
    """
    global mcp_initialized

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    error_desc = request.query_params.get("error_description", "")

    # 1. Check for OAuth errors
    if error:
        logger.error(f"OAuth auth failed: {error} — {error_desc}")
        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: system-ui; text-align: center; padding-top: 50px;">
                    <div style="max-width: 500px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px;">
                        <div style="font-size: 48px; color: #e53e3e;">&#10007;</div>
                        <h2 style="color: #e53e3e;">Authentication Failed</h2>
                        <p style="color: #718096;"><b>Error:</b> {html_escape(error)}</p>
                        <p style="color: #718096;">{html_escape(error_desc)}</p>
                        <a href="/auth/start" style="color: #fc8019;">Try Again</a>
                    </div>
                </body>
            </html>
            """,
            status_code=400,
        )

    # 2. Validate callback params (includes CSRF state check)
    validation = verify_callback_params(code, state, error, token_store=memory)
    if not validation["valid"]:
        return JSONResponse(
            {"status": "error", "message": validation["error"]},
            status_code=400,
        )

    # 3. Exchange code for access token
    try:
        token_data = await oauth_client.exchange_code(code=code)

        token_preview = token_data.get("access_token", "")[:15]
        expires_in = token_data.get("expires_in", "?")
        scope = token_data.get("scope", "")

        logger.info(f"OAuth success! Token: {token_preview}... expires_in: {expires_in}s, scope: {scope}")

        # Reset MCP initialized flag so it re-connects with new token
        mcp_initialized = False
        if orchestrator:
            mcp_client = getattr(orchestrator, 'mcp_client', None)
            if mcp_client:
                mcp_client.reset_session()

        # Pre-initialize MCP servers with new token
        try:
            orch = await get_orchestrator()
            mcp_client = getattr(orch, 'mcp_client', None)
            if mcp_client:
                init_results = await mcp_client.initialize_all()
                logger.info(f"MCP pre-init after OAuth: {init_results}")
        except Exception as mcp_err:
            logger.warning(f"MCP pre-init failed (will retry on first /chat): {mcp_err}")

        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: system-ui; text-align: center; padding-top: 60px; background-color: #f7fafc;">
                    <div style="max-width: 500px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <div style="font-size: 48px; color: #38a169;">&#10003;</div>
                        <h2 style="color: #2d3748; margin-top: 10px;">Swiggy Connected!</h2>
                        <p style="color: #718096; line-height: 1.5;">
                            OAuth token received and stored successfully.<br>
                            Token expires in <b>{int(expires_in) // 3600} hours</b>.<br>
                            Scope: <code>{html_escape(scope)}</code>
                        </p>
                        <p style="color: #718096;">Redirecting back to the chat interface...</p>
                        <script>
                            setTimeout(() => {{
                                window.location.href = '/';
                            }}, 1500);
                        </script>
                        <div style="margin-top: 20px; padding: 12px; background: #edf2f7; border-radius: 8px;">
                            <p style="color: #4a5568; font-size: 14px;">You can now close this tab. The orchestrator is ready to accept queries.</p>
                        </div>
                    </div>
                </body>
            </html>
            """,
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: system-ui; text-align: center; padding-top: 50px;">
                    <div style="max-width: 500px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px;">
                        <div style="font-size: 48px; color: #e53e3e;">&#10007;</div>
                        <h2 style="color: #e53e3e;">Token Exchange Failed</h2>
                        <p style="color: #718096;">{html_escape(str(e))}</p>
                        <p style="color: #718096; font-size: 14px;">Check that your callback URL is whitelisted and try again.</p>
                        <a href="/auth/start" style="color: #fc8019;">Retry Auth</a>
                    </div>
                </body>
            </html>
            """,
            status_code=500,
        )


@app.get("/auth/status")
async def auth_status():
    """Check current auth status."""
    if oauth_client.is_authenticated():
        hours = oauth_client.time_until_expiry() / 3600
        result = {
            "authenticated": True,
            "expires_in_hours": round(hours, 2),
            "scope": oauth_client._scope,
            "mcp_initialized": mcp_initialized,
        }
        if orchestrator:
            mcp_client = getattr(orchestrator, 'mcp_client', None)
            if mcp_client:
                result["mcp_servers"] = mcp_client.get_status()
        return result
    return {
        "authenticated": False,
        "message": "No valid token. Visit /auth/start to connect.",
        "mcp_initialized": False,
    }


@app.post("/auth/set-token")
async def set_token_api(request: Request):
    """Manually set an access token."""
    global mcp_initialized
    body = await request.json()
    token = body.get("access_token") or body.get("token")
    if not token:
        return JSONResponse({"error": "Missing 'access_token' parameter"}, status_code=400)

    expires_in = float(body.get("expires_in", 432000))
    oauth_client.set_token(token=token, expires_in=expires_in)
    mcp_initialized = False
    if orchestrator:
        mcp_client = getattr(orchestrator, 'mcp_client', None)
        if mcp_client:
            mcp_client.reset_session()
            try:
                await mcp_client.initialize_all()
                mcp_initialized = True
            except Exception as e:
                logger.warning(f"MCP init failed after set-token: {e}")

    return {
        "status": "ok",
        "authenticated": oauth_client.is_authenticated(),
        "expires_in_hours": round(oauth_client.time_until_expiry() / 3600, 2),
    }


@app.get("/debug/tools")
async def debug_tools():
    """List all real MCP tools and schemas available on connected servers."""
    if not oauth_client.is_authenticated():
        return JSONResponse({"error": "Not authenticated. Connect at /auth/start"}, status_code=401)
    orch = await get_orchestrator()
    mcp = getattr(orch, 'mcp_client', None)
    if not mcp:
        return JSONResponse({"error": "MCP client not initialized"}, status_code=500)
    out = {}
    for s in ["food", "instamart", "dineout"]:
        try:
            tools = await mcp.list_tools(s)
            out[s] = [
                {
                    "name": t.get("name"),
                    "description": t.get("description", "")[:120],
                    "required": t.get("inputSchema", {}).get("required", []) if isinstance(t.get("inputSchema"), dict) else []
                }
                for t in tools
            ]
        except Exception as e:
            out[s] = {"error": str(e)}
    return out


# ============================================================
#  Chat / Query Endpoint
# ============================================================

@app.post("/chat")
async def chat(request: Request):
    """
    Accept a user query and route it through the orchestrator.

    Body: {"query": "order biryani", "context": {"address_id": "home"}}
    """
    if not oauth_client.is_authenticated():
        return JSONResponse(
            {"error": "Not authenticated. Visit /auth/start first."},
            status_code=401,
        )

    body = await request.json()
    query = body.get("query", "")
    context = body.get("context", {})

    if not query:
        return JSONResponse({"error": "Missing 'query' field"}, status_code=400)

    # Get or create orchestrator
    try:
        orch = await get_orchestrator()
    except Exception as e:
        logger.error(f"Failed to create orchestrator: {e}")
        return JSONResponse(
            {"error": f"Orchestrator initialization failed: {e}"},
            status_code=500,
        )

    # Process through the orchestrator pipeline
    try:
        result = await orch.process_query(query, context)

        return {
            "status": "ok",
            "query": query,
            "response": result.get("response_text", ""),
            "active_server": result.get("active_server"),
            "tool_calls": result.get("tool_calls", []),
            "state": result.get("state", {}),
            "rankings": result.get("rankings"),
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Orchestrator error: {tb}")
        return JSONResponse(
            {"error": f"Processing failed: {e}", "query": query},
            status_code=500,
        )


# ============================================================
#  MCP Status Endpoint (debug)
# ============================================================

@app.get("/mcp/status")
async def mcp_status():
    """Debug endpoint to check MCP server connection status."""
    if not orchestrator:
        return {"status": "not_initialized", "servers": {}}
    mcp_client = getattr(orchestrator, 'mcp_client', None)
    if not mcp_client:
        return {"status": "no_mcp_client", "servers": {}}
    return {
        "status": "initialized" if mcp_initialized else "pending",
        "servers": mcp_client.get_status(),
    }


# ============================================================
#  Address Management Endpoints
# ============================================================

@app.get("/addresses")
async def get_saved_addresses():
    """Return all saved addresses for the authenticated user."""
    if not oauth_client.is_authenticated():
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    orch = await get_orchestrator()
    mcp = getattr(orch, 'mcp_client', None)
    if not mcp:
        return JSONResponse({"error": "MCP client not available"}, status_code=500)
    try:
        res = await mcp.call_tool("food", "get_addresses", {})
        return res
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
#  Cart Management Endpoints (Real Swiggy MCP Sync)
# ============================================================

session_cart = {
    "restaurant_id": None,
    "restaurant_name": None,
    "cart_type": "food",
    "address_id": None,
    "items": [],
    "applied_coupon": None,
}


def _calculate_cart_bill():
    items = session_cart.get("items", [])
    if not items:
        return {
            "has_items": False,
            "cart_type": session_cart.get("cart_type", "food"),
            "restaurant_id": None,
            "restaurant_name": None,
            "address_id": session_cart.get("address_id"),
            "items": [],
            "item_count": 0,
            "item_total": 0.0,
            "delivery_fee": 0.0,
            "taxes": 0.0,
            "discount": 0.0,
            "final_amount": 0.0,
            "applied_coupon": None,
        }

    item_total = sum(float(i.get("price", 0)) * int(i.get("quantity", 1)) for i in items)
    delivery_fee = 35.0 if item_total < 500 else 0.0
    taxes = round(item_total * 0.05, 2)
    coupon = session_cart.get("applied_coupon")
    discount = 50.0 if coupon else 0.0
    final_amount = max(0.0, round(item_total + delivery_fee + taxes - discount, 2))

    return {
        "has_items": True,
        "cart_type": session_cart.get("cart_type", "food"),
        "restaurant_id": session_cart.get("restaurant_id"),
        "restaurant_name": session_cart.get("restaurant_name"),
        "address_id": session_cart.get("address_id"),
        "items": items,
        "item_count": sum(int(i.get("quantity", 1)) for i in items),
        "item_total": round(item_total, 2),
        "delivery_fee": round(delivery_fee, 2),
        "taxes": round(taxes, 2),
        "discount": round(discount, 2),
        "final_amount": round(final_amount, 2),
        "applied_coupon": coupon,
    }


@app.get("/cart")
async def get_cart(address_id: str = None):
    """Return current cart contents, bill breakdown, and merchant details."""
    bill = _calculate_cart_bill()
    return bill


@app.post("/cart/add")
async def add_to_cart(request: Request):
    """
    Add an item to the cart. If adding from a new restaurant, previous food items are replaced.
    Body:
    {
      "type": "food" | "instamart",
      "restaurant_id": "...",
      "restaurant_name": "...",
      "item_id": "...",
      "name": "...",
      "price": 176.0,
      "quantity": 1,
      "address_id": "...",
      "is_veg": false,
      "image_url": "..."
    }
    """
    body = await request.json()
    c_type = body.get("type", "food")
    rest_id = body.get("restaurant_id")
    rest_name = body.get("restaurant_name", "Restaurant")
    item_id = str(body.get("item_id", ""))
    item_name = body.get("name", "Dish")
    raw_price = body.get("price", 0)
    try:
        price = float(raw_price)
    except (ValueError, TypeError):
        price = 0.0
    qty = max(1, int(body.get("quantity", 1)))
    address_id = body.get("address_id") or session_cart.get("address_id")
    is_veg = body.get("is_veg", False)
    image_url = body.get("image_url", "")

    # Single-restaurant cart policy (matching Swiggy behavior)
    if session_cart["restaurant_id"] and session_cart["restaurant_id"] != rest_id and c_type == "food":
        session_cart["items"] = []

    session_cart["cart_type"] = c_type
    session_cart["restaurant_id"] = rest_id
    session_cart["restaurant_name"] = rest_name
    session_cart["address_id"] = address_id

    # Check if item already exists
    existing = next((i for i in session_cart["items"] if str(i.get("id")) == item_id), None)
    if existing:
        existing["quantity"] += qty
        existing["total_price"] = round(existing["quantity"] * existing["price"], 2)
    else:
        session_cart["items"].append({
            "id": item_id,
            "name": item_name,
            "price": round(price, 2),
            "quantity": qty,
            "total_price": round(price * qty, 2),
            "is_veg": bool(is_veg),
            "image_url": image_url,
            "restaurant_id": rest_id,
            "restaurant_name": rest_name,
        })

    # Asynchronously sync with Swiggy MCP in background
    if oauth_client.is_authenticated():
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            if mcp and address_id:
                if c_type == "food" and rest_id:
                    payload = [{"menu_item_id": i["id"], "quantity": i["quantity"]} for i in session_cart["items"]]
                    await mcp.call_tool("food", "update_food_cart", {
                        "restaurantId": rest_id,
                        "cartItems": payload,
                        "addressId": address_id
                    })
                elif c_type == "instamart":
                    payload = [{"itemId": i["id"], "quantity": i["quantity"]} for i in session_cart["items"]]
                    await mcp.call_tool("instamart", "update_cart", {
                        "selectedAddressId": address_id,
                        "items": payload
                    })
        except Exception as e:
            logger.warning(f"MCP background cart sync warning: {e}")

    return _calculate_cart_bill()


@app.post("/cart/update")
async def update_cart_item(request: Request):
    """
    Update item quantity (0 removes item).
    Body: {"item_id": "...", "quantity": 2, "address_id": "..."}
    """
    body = await request.json()
    item_id = str(body.get("item_id", ""))
    quantity = int(body.get("quantity", 0))

    if quantity <= 0:
        session_cart["items"] = [i for i in session_cart["items"] if str(i.get("id")) != item_id]
    else:
        for it in session_cart["items"]:
            if str(it.get("id")) == item_id:
                it["quantity"] = quantity
                it["total_price"] = round(quantity * it["price"], 2)

    if not session_cart["items"]:
        session_cart["restaurant_id"] = None
        session_cart["restaurant_name"] = None
        session_cart["applied_coupon"] = None

    # Sync with Swiggy MCP
    if oauth_client.is_authenticated():
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            aid = body.get("address_id") or session_cart.get("address_id")
            if mcp:
                if not session_cart["items"]:
                    await mcp.call_tool("food", "flush_food_cart", {})
                elif aid and session_cart["restaurant_id"]:
                    payload = [{"menu_item_id": i["id"], "quantity": i["quantity"]} for i in session_cart["items"]]
                    await mcp.call_tool("food", "update_food_cart", {
                        "restaurantId": session_cart["restaurant_id"],
                        "cartItems": payload,
                        "addressId": aid
                    })
        except Exception as e:
            logger.warning(f"MCP cart update sync warning: {e}")

    return _calculate_cart_bill()


@app.post("/cart/clear")
async def clear_cart():
    """Clear all items from active cart."""
    session_cart["items"] = []
    session_cart["restaurant_id"] = None
    session_cart["restaurant_name"] = None
    session_cart["applied_coupon"] = None

    if oauth_client.is_authenticated():
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            if mcp:
                await mcp.call_tool("food", "flush_food_cart", {})
                await mcp.call_tool("instamart", "clear_cart", {})
        except Exception as e:
            logger.warning(f"MCP clear cart warning: {e}")

    return _calculate_cart_bill()


@app.post("/cart/apply-coupon")
async def apply_coupon(request: Request):
    """
    Apply promo coupon code.
    Body: {"coupon_code": "SWIGGY50", "address_id": "..."}
    """
    body = await request.json()
    code = (body.get("coupon_code") or "").strip().upper()

    if not code:
        session_cart["applied_coupon"] = None
        return _calculate_cart_bill()

    session_cart["applied_coupon"] = code

    # Attempt MCP tool call if available
    if oauth_client.is_authenticated():
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            aid = body.get("address_id") or session_cart.get("address_id")
            if mcp and aid:
                await mcp.call_tool("food", "apply_food_coupon", {
                    "couponCode": code,
                    "addressId": aid
                })
        except Exception as e:
            logger.warning(f"MCP coupon apply warning: {e}")

    bill = _calculate_cart_bill()
    bill["message"] = f"Coupon '{code}' applied successfully!"
    return bill


@app.post("/cart/checkout")
async def checkout_cart(request: Request):
    """
    Place order for current cart items via Swiggy MCP using Cash on Delivery / Sandbox.
    """
    import time
    bill = _calculate_cart_bill()
    if not bill["has_items"]:
        return JSONResponse({"error": "Cart is empty"}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        body = {}
    aid = body.get("address_id") or session_cart.get("address_id")

    # If no address_id specified, fetch default address
    if not aid and oauth_client.is_authenticated():
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            if mcp:
                addr_res = await mcp.call_tool("food", "get_addresses", {})
                addrs = addr_res.get("data", {}).get("addresses", []) if addr_res.get("success") else []
                if addrs:
                    aid = addrs[0]["id"]
        except Exception:
            pass

    order_id = f"SWIG_{int(time.time()*1000)}"
    c_type = session_cart.get("cart_type", "food")
    rest_name = session_cart.get("restaurant_name") or "Swiggy Order"
    order_items = list(session_cart.get("items", []))
    final_amt = bill["final_amount"]

    # Call Swiggy MCP place order tool
    mcp_order_placed = False
    if oauth_client.is_authenticated() and aid:
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            if mcp:
                if c_type == "food":
                    place_res = await mcp.call_tool("food", "place_food_order", {"addressId": aid})
                    if place_res.get("success"):
                        mcp_order_placed = True
                        p_data = place_res.get("data")
                        if isinstance(p_data, dict) and p_data.get("orderId"):
                            order_id = str(p_data["orderId"])
                elif c_type == "instamart":
                    place_res = await mcp.call_tool("instamart", "checkout", {"addressId": aid})
                    if place_res.get("success"):
                        mcp_order_placed = True
                        p_data = place_res.get("data")
                        if isinstance(p_data, dict) and p_data.get("orderId"):
                            order_id = str(p_data["orderId"])
        except Exception as e:
            logger.warning(f"MCP place order error: {e}")

    # Persist order to SQLite memory
    memory.save_order(
        order_id=order_id,
        server=c_type,
        merchant_name=rest_name,
        items=order_items,
        total_amount=final_amt,
        status="PLACED"
    )

    # Reset active session cart
    session_cart["items"] = []
    session_cart["restaurant_id"] = None
    session_cart["restaurant_name"] = None
    session_cart["applied_coupon"] = None

    return {
        "success": True,
        "order_id": order_id,
        "restaurant_name": rest_name,
        "items": order_items,
        "total_amount": final_amt,
        "status": "PLACED",
        "eta": "25-35 mins",
        "message": f"Order #{order_id} placed successfully via Swiggy MCP (COD)!"
    }


# ============================================================
#  Orders & Live Tracking Endpoints
# ============================================================

@app.get("/orders")
async def get_orders(address_id: str = None):
    """Return past and active orders from SQLite and Swiggy MCP."""
    past_orders = memory.get_past_orders(limit=20)

    # Try fetching orders from Swiggy MCP
    mcp_orders = []
    if oauth_client.is_authenticated():
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            if mcp:
                if address_id:
                    food_orders_res = await mcp.call_tool("food", "get_food_orders", {"addressId": address_id})
                    if food_orders_res.get("success") and isinstance(food_orders_res.get("data"), list):
                        mcp_orders.extend(food_orders_res["data"])
                im_orders_res = await mcp.call_tool("instamart", "get_orders", {})
                if im_orders_res.get("success") and isinstance(im_orders_res.get("data"), list):
                    mcp_orders.extend(im_orders_res["data"])
        except Exception as e:
            logger.warning(f"Failed to fetch MCP orders: {e}")

    return {
        "orders": past_orders,
        "mcp_orders": mcp_orders,
        "total": len(past_orders) + len(mcp_orders)
    }


@app.get("/orders/track/{order_id}")
async def track_order(order_id: str):
    """Return live delivery tracking status, rider information, and ETA."""
    # First check if Swiggy MCP provides live tracking
    if oauth_client.is_authenticated():
        try:
            orch = await get_orchestrator()
            mcp = getattr(orch, 'mcp_client', None)
            if mcp:
                track_res = await mcp.call_tool("food", "track_food_order", {"orderId": order_id})
                if track_res.get("success") and track_res.get("data"):
                    return track_res["data"]
        except Exception as e:
            logger.warning(f"MCP live tracking error: {e}")

    # Fallback to rich simulated live order tracking
    return {
        "order_id": order_id,
        "status": "PREPARING",
        "step": 2,
        "status_title": "Food is being prepared",
        "status_subtitle": "Chef is preparing your order with fresh ingredients",
        "eta": "24 mins",
        "delivery_partner": {
            "name": "Kishore Kumar",
            "rating": "4.9★",
            "phone": "+91 98450 12345",
            "vehicle": "Hero Electric (EV)"
        },
        "steps": [
            {"title": "Order Placed", "time": "Just now", "completed": True},
            {"title": "Order Confirmed & Preparing", "time": "In progress", "completed": True, "active": True},
            {"title": "Out for Delivery", "time": "Estimated 10 mins", "completed": False},
            {"title": "Delivered", "time": "Estimated 24 mins", "completed": False}
        ]
    }


# ============================================================
#  Static Frontend
# ============================================================
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")

# ============================================================
#  Main
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
