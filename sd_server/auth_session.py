import secrets
import base64
import hashlib
import time
from threading import Lock
from typing import Optional

from flask import (
    make_response,
    render_template_string,
)

AUTH_SESSION_TTL_S = 180

_CALLBACK_HTML = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{{ title }}</title>
    <style>
      body { font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 14vh; color: #1f2328; }
      .card { display: inline-block; padding: 2rem 2.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
      h2 { margin: 0 0 0.5rem; color: {{ '#1D0B77' if success else '#d93025' }}; }
      p { margin: 0; color: #57606a; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>{{ title }}</h2>
      <p>{{ message }}</p>
    </div>
    {% if success %}
    <script>setTimeout(() => window.close(), 1500);</script>
    {% endif %}
  </body>
</html>"""



def render_callback_html(title: str, message: str, status_code: int, success: bool = False):
    html = render_template_string(
        _CALLBACK_HTML, title=title, message=message, success=success
    )
    resp = make_response(html, status_code)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp

class AuthSessionStore:
    """Thread-safe state machine for the desktop OAuth + PKCE handshake."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._status = "idle"  # "idle" | "pending" | "authenticated" | "error"
        self._error: Optional[str] = None
        self._local_code: Optional[str] = None
        self._code_verifier: Optional[str] = None
        self._redirect_uri: Optional[str] = None
        self._expires_at: float = 0.0

    def start(self, redirect_uri: str) -> dict:
        local_code = secrets.token_hex(32)
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        with self._lock:
            self._status = "pending"
            self._error = None
            self._local_code = local_code
            self._code_verifier = code_verifier
            self._redirect_uri = redirect_uri
            self._expires_at = time.time() + AUTH_SESSION_TTL_S

        return {
            "client": "sundial",
            "state": local_code,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

    def consume_for_callback(self, returned_local_code: str):
        with self._lock:
            expected_code = self._local_code
            code_verifier = self._code_verifier
            redirect_uri = self._redirect_uri
            expired = time.time() > self._expires_at

            self._local_code = None
            self._code_verifier = None

            if not expected_code or not code_verifier or expired:
                self._status = "error"
                self._error = "Login session expired. Please return to the app and try again."
                return None, None, self._error

            if not secrets.compare_digest(returned_local_code, expected_code):
                self._status = "error"
                self._error = "Invalid session state (local_code mismatch)."
                return None, None, self._error

            return code_verifier, redirect_uri, None

    def mark_authenticated(self) -> None:
        with self._lock:
            self._status = "authenticated"
            self._error = None

    def mark_error(self, message: str) -> None:
        with self._lock:
            self._status = "error"
            self._error = message
            self._local_code = None
            self._code_verifier = None

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "authenticated": self._status == "authenticated",
                "error": self._error,
            }


# Shared singleton instance imported by the Flask route resources
auth_store = AuthSessionStore()
