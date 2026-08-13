"""
OAuth 2.1 PKCE client for Swiggy MCP Servers.

Handles:
  0. Dynamic Client Registration (RFC 7591) — gets your client_id automatically
  1. PKCE verifier/challenge generation
  2. Authorization URL construction
  3. Token exchange (code -> access_token)
  4. Token storage and refresh lifecycle

Swiggy uses OAuth 2.1 with PKCE (S256) over streamable HTTP.
One OAuth token works across all three servers (food, instamart, dineout).
No refresh token in v1.0 — re-run auth on expiry (~5 day access token).

Auth endpoints (from /.well-known/oauth-authorization-server):
  GET  /auth/authorize       — consent UI
  POST /auth/token          — code → token exchange
  POST /auth/register       — Dynamic Client Registration (RFC 7591)
  POST /auth/logout         — revoke session
"""

import hashlib
import base64
import secrets
import time
import logging
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)


def generate_code_verifier() -> str:
    """Generate a high-entropy PKCE code verifier (43-128 chars)."""
    return secrets.token_urlsafe(64)


def generate_code_challenge(verifier: str) -> str:
    """S256 challenge: BASE64URL(SHA256(verifier))."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class SwiggyOAuthClient:
    """
    Full OAuth 2.1 PKCE flow for Swiggy MCP — with Dynamic Client Registration.

    Usage:
        oauth = SwiggyOAuthClient(
            redirect_uri="https://your-app.onrender.com/oauth/callback",
            client_name="MCP Orchestrator",
        )

        # Step 0: Register — gets client_id from Swiggy automatically
        await oauth.register_client()

        # Step 1: Generate auth URL
        auth_url = oauth.authorization_url()

        # Step 2: After user authorizes, exchange code for token
        token_data = await oauth.exchange_code(code="received_code")

        # Step 3: Use token
        token = oauth.get_token()  # Bearer token for MCP calls
    """

    # Swiggy MCP auth base URL
    AUTH_BASE = "https://mcp.swiggy.com"

    def __init__(
        self,
        redirect_uri: str,
        client_name: str = "MCP Orchestrator",
        client_id: Optional[str] = None,
        token_store: Optional[Any] = None,
    ):
        self.redirect_uri = redirect_uri
        self.client_name = client_name
        self.client_id = client_id  # can be None — will DCR on register_client()
        self.client_secret: Optional[str] = None
        self.token_store = token_store

        # PKCE
        self._verifier: Optional[str] = None
        self._challenge: Optional[str] = None

        # Token
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._scope: Optional[str] = None

    # ================================================================
    #  Step 0: Dynamic Client Registration (RFC 7591)
    # ================================================================

    async def register_client(
        self,
        redirect_uris: Optional[List[str]] = None,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Register this client with Swiggy's OAuth server via DCR.

        Returns the client registration response including client_id.
        You do NOT need to manually apply for a client_id — this call
        creates one for you automatically.

        Per RFC 7591: POST /auth/register with:
          - client_name
          - redirect_uris (exact-match, HTTPS required)
          - grant_types
          - response_types
          - scope
          - token_endpoint_auth_method

        Returns: {"client_id": "...", "client_secret": "...", "client_id_issued_at": ..., ...}
        """
        uris = redirect_uris or [self.redirect_uri]
        requested_scopes = scopes or ["mcp:tools", "mcp:resources", "mcp:prompts"]

        registration_payload = {
            "client_name": self.client_name,
            "redirect_uris": uris,
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "scope": " ".join(requested_scopes),
            "token_endpoint_auth_method": "client_secret_post",
            # PKCE required
            "code_challenge_method": "S256",
        }

        register_url = f"{self.AUTH_BASE}/auth/register"
        logger.info(f"Registering client '{self.client_name}' with Swiggy DCR...")
        logger.info(f"  Redirect URIs: {uris}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    register_url,
                    json=registration_payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                reg_data = resp.json()

            self.client_id = reg_data.get("client_id")
            self.client_secret = reg_data.get("client_secret")

            # Persist registration to SQLite
            if self.token_store and hasattr(self.token_store, "set_preference"):
                self.token_store.set_preference("swiggy_client_id", self.client_id)
                if self.client_secret:
                    self.token_store.set_preference("swiggy_client_secret", self.client_secret)

            logger.info(f"Client registered! client_id: {self.client_id}")
            return reg_data

        except httpx.HTTPStatusError as e:
            logger.error(f"DCR failed ({e.response.status_code}): {e.response.text}")
            raise RuntimeError(
                f"Dynamic Client Registration failed: {e.response.status_code} — "
                f"{e.response.text}. Ensure your redirect URI is HTTPS and whitelisted."
            ) from e
        except httpx.ConnectError as e:
            logger.error(f"Cannot reach Swiggy auth server: {e}")
            raise RuntimeError(f"Cannot reach {register_url}. Check network connectivity.") from e

    def restore_registration(self) -> bool:
        """Try to restore client_id from store (skip re-registration)."""
        if not self.token_store or not hasattr(self.token_store, "get_preference"):
            return False

        saved_id = self.token_store.get_preference("swiggy_client_id")
        if saved_id:
            self.client_id = saved_id
            self.client_secret = self.token_store.get_preference("swiggy_client_secret")
            logger.info(f"Client registration restored: {self.client_id}")
            return True
        return False

    # ================================================================
    #  Step 1: Authorization URL
    # ================================================================

    def _ensure_pkce(self):
        """Generate PKCE verifier/challenge if not already done."""
        if not self._verifier:
            self._verifier = generate_code_verifier()
            self._challenge = generate_code_challenge(self._verifier)

    def authorization_url(
        self,
        scope: str = "mcp:tools mcp:resources mcp:prompts",
        state: Optional[str] = None,
    ) -> str:
        """
        Build the Swiggy OAuth authorization URL.

        Per Swiggy docs: GET /auth/authorize (NOT per-server, shared auth endpoint).
        """
        if not self.client_id:
            raise RuntimeError(
                "No client_id. Call register_client() first, or pass client_id to constructor."
            )

        self._ensure_pkce()
        if not state:
            state = secrets.token_urlsafe(32)
            # Save state for CSRF validation
            if self.token_store and hasattr(self.token_store, "set_preference"):
                self.token_store.set_preference("oauth_state", state)

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_challenge": self._challenge,
            "code_challenge_method": "S256",
            "scope": scope,
            "state": state,
        }

        # Shared auth endpoint (not per-server)
        auth_url = f"{self.AUTH_BASE}/auth/authorize?{urlencode(params)}"
        logger.info(f"Auth URL generated. client_id: {self.client_id[:15]}...")
        return auth_url

    # ================================================================
    #  Step 2: Code Exchange
    # ================================================================

    async def exchange_code(
        self,
        code: str,
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Per Swiggy docs: POST /auth/token (shared, not per-server).
        Uses JSON body per their example curl.

        Token response:
          {"access_token": "eyJ...", "token_type": "Bearer", "expires_in": 432000, "scope": "..."}
        """
        if not self.client_id:
            raise RuntimeError("No client_id. Call register_client() first.")

        self._ensure_pkce()

        # Shared token endpoint
        token_url = f"{self.AUTH_BASE}/auth/token"

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": self._verifier,
        }

        # Add client_secret if we got one from DCR
        if self.client_secret:
            payload["client_secret"] = self.client_secret

        logger.info("Exchanging code for token...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                token_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            token_data = resp.json()

        # Validate
        if "access_token" not in token_data:
            raise ValueError(f"Token response missing access_token: {token_data}")

        # Store in memory
        self._access_token = token_data["access_token"]
        self._token_expires_at = time.time() + token_data.get("expires_in", 432000)
        self._scope = token_data.get("scope", "")

        # Persist to SQLite
        self._persist_token(token_data)

        logger.info(f"Token received. Expires in {token_data.get('expires_in', '?')}s. Scope: {self._scope}")

        # Rotate PKCE for next auth
        self._verifier = None
        self._challenge = None

        return token_data

    # ================================================================
    #  Token Management
    # ================================================================

    def get_token(self) -> Optional[str]:
        """Get the current access token. Returns None if expired or not set."""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        if self._access_token:
            logger.warning("Token expired. Need to re-authenticate.")
        return None

    def is_authenticated(self) -> bool:
        """Check if we have a valid (non-expired) token."""
        return self.get_token() is not None

    def time_until_expiry(self) -> float:
        """Seconds until token expires. Negative means expired."""
        return self._token_expires_at - time.time()

    def get_auth_headers(self) -> Dict[str, str]:
        """Get Authorization headers for MCP calls."""
        token = self.get_token()
        if not token:
            raise RuntimeError("No valid token. Run OAuth flow first.")
        return {"Authorization": f"Bearer {token}"}

    def _persist_token(self, token_data: Dict[str, Any]):
        """Persist token data to SQLite via MemoryManager."""
        if self.token_store and hasattr(self.token_store, "set_preference"):
            self.token_store.set_preference("swiggy_access_token", token_data["access_token"])
            self.token_store.set_preference("swiggy_token_expires_at", str(self._token_expires_at))
            self.token_store.set_preference("swiggy_token_scope", self._scope)
            logger.info("Token persisted to store")

    def restore_from_store(self) -> bool:
        """Restore token from store on startup."""
        if not self.token_store or not hasattr(self.token_store, "get_preference"):
            return False

        token = self.token_store.get_preference("swiggy_access_token")
        expires_at = self.token_store.get_preference("swiggy_token_expires_at")

        if token and expires_at:
            self._access_token = token
            self._token_expires_at = float(expires_at)
            if self.is_authenticated():
                logger.info("Token restored from store. Still valid.")
                return True
            else:
                logger.info("Token restored from store but expired.")
                self._access_token = None
        return False

    def get_registration_info(self) -> Dict[str, Any]:
        """Return current registration status for debugging."""
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "redirect_uri": self.redirect_uri,
            "has_secret": bool(self.client_secret),
            "authenticated": self.is_authenticated(),
            "token_expires_in_hours": self.time_until_expiry() / 3600 if self.is_authenticated() else None,
            "scope": self._scope,
        }


def verify_callback_params(code: Optional[str], state: Optional[str], error: Optional[str]) -> Dict[str, Any]:
    """Validate OAuth callback parameters."""
    if error:
        return {"valid": False, "error": f"OAuth error: {error}"}
    if not code:
        return {"valid": False, "error": "Missing authorization code"}
    return {"valid": True, "code": code, "state": state}
