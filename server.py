from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import logging
from orchestrator.memory import MemoryManager

app = FastAPI(title="Swiggy MCP Orchestrator OAuth Server")
logger = logging.getLogger(__name__)
memory = MemoryManager()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <body style="font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 50px; background-color: #f7fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h1 style="color: #fc8019; margin-bottom: 5px;">Swiggy MCP Orchestrator</h1>
                <p style="color: #718096; font-size: 16px;">OAuth Callback & Authentication Server</p>
                <div style="margin: 30px 0; padding: 15px; background: #edf2f7; border-radius: 8px; text-align: left;">
                    <p style="margin: 5px 0;"><b>Server Status:</b> <span style="color: #38a169; font-weight: bold;">● Active & Running</span></p>
                    <p style="margin: 5px 0;"><b>Port:</b> 8000</p>
                    <p style="margin: 5px 0;"><b>OAuth Callback URL:</b> <code>/oauth/callback</code></p>
                </div>
                <a href="/oauth/callback?code=swiggy_demo_code_123" style="display: inline-block; background-color: #fc8019; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Test OAuth Callback Redirect →</a>
            </div>
        </body>
    </html>
    """

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Swiggy MCP Orchestrator OAuth Server"}


@app.get("/oauth/callback")
@app.get("/callback")
async def oauth_callback(request: Request):

    """
    OAuth Callback Endpoint for Swiggy Builder's Club.
    Receives authorization code from Swiggy OAuth redirect, saves it to SQLite memory,
    and displays a success screen.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        logger.error(f"OAuth Authentication Failed: {error}")
        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                    <h2 style="color: #e53e3e;">Authentication Failed</h2>
                    <p>Error: {error}</p>
                </body>
            </html>
            """,
            status_code=400
        )

    if not code:
        return JSONResponse({"status": "error", "message": "Missing authorization code"}, status_code=400)

    # Save OAuth code & state to SQLite database memory
    memory.set_preference("oauth_code", code)
    if state:
        memory.set_preference("oauth_state", state)

    logger.info(f"OAuth code successfully received and saved to DB: {code[:10]}...")

    return HTMLResponse(
        content="""
        <html>
            <body style="font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 60px; background-color: #f7fafc;">
                <div style="max-width: 500px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="font-size: 48px; color: #38a169;">✓</div>
                    <h2 style="color: #2d3748; margin-top: 10px;">Authentication Successful!</h2>
                    <p style="color: #718096; line-height: 1.5;">Swiggy OAuth credentials have been saved to the Orchestrator memory.</p>
                    <p style="color: #e53e3e; font-weight: 600; margin-top: 20px;">You can now close this tab and return to the terminal CLI.</p>
                </div>
            </body>
        </html>
        """,
        status_code=200
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
