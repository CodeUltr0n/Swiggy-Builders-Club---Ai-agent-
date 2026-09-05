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

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from orchestrator.memory import MemoryManager
from orchestrator.oauth import SwiggyOAuthClient, verify_callback_params
from orchestrator.init_orchestrator import create_orchestrator

# --- Config from env ---
REDIRECT_URI = os.getenv("SWIGGY_REDIRECT_URI", "https://swiggy-builders-club-ai-agent.onrender.com/oauth/callback")
CLIENT_NAME = os.getenv("SWIGGY_CLIENT_NAME", "MCP Orchestrator")

app = FastAPI(title="Swiggy MCP Orchestrator")
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

@app.get("/", response_class=HTMLResponse)
async def root():
    auth_status = "Authenticated" if oauth_client.is_authenticated() else "Not Authenticated"
    expiry = ""
    if oauth_client.is_authenticated():
        hours_left = oauth_client.time_until_expiry() / 3600
        expiry = f" ({hours_left:.1f}h remaining)"

    mcp_status = "Connected" if mcp_initialized else "Pending"
    client_id_display = html_escape(oauth_client.client_id or "Not registered yet")

    return f"""
    <html>
        <body style="font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 50px; background-color: #f7fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h1 style="color: #fc8019; margin-bottom: 5px;">Swiggy MCP Orchestrator</h1>
                <p style="color: #718096; font-size: 16px;">AI-Powered Commerce Agent</p>
                <div style="margin: 30px 0; padding: 15px; background: #edf2f7; border-radius: 8px; text-align: left;">
                    <p style="margin: 5px 0;"><b>Server Status:</b> <span style="color: #38a169; font-weight: bold;">&#9679; Active</span></p>
                    <p style="margin: 5px 0;"><b>Auth Status:</b> <span style="color: {'#38a169' if oauth_client.is_authenticated() else '#e53e3e'}; font-weight: bold;">{html_escape(auth_status)}{html_escape(expiry)}</span></p>
                    <p style="margin: 5px 0;"><b>MCP Servers:</b> <span style="color: {'#38a169' if mcp_initialized else '#d69e2e'}; font-weight: bold;">{html_escape(mcp_status)}</span></p>
                    <p style="margin: 5px 0;"><b>OAuth Callback:</b> <code>/oauth/callback</code></p>
                    <p style="margin: 5px 0;"><b>Redirect URI:</b> <code>{html_escape(REDIRECT_URI)}</code></p>
                    <p style="margin: 5px 0;"><b>Client ID:</b> <code>{client_id_display}</code></p>
                </div>
    {'                <p style="color: #38a169; font-weight: 600;">&#10003; Token active. Ready to accept queries.</p>' if oauth_client.is_authenticated() else '                <a href="/auth/start" style="display: inline-block; background-color: #fc8019; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 10px;">Connect Swiggy Account &#8594;</a>'}
            </div>
        </body>
    </html>
    """


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
        logger.error(f"Orchestrator error: {e}", exc_info=True)
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
#  Shutdown
# ============================================================

@app.on_event("shutdown")
async def shutdown():
    if orchestrator:
        mcp_client = getattr(orchestrator, 'mcp_client', None)
        if mcp_client:
            await mcp_client.close()
    logger.info("Orchestrator shutdown complete")


# ============================================================
#  Main
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
