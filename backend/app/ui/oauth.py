# app/ui/oauth.py
"""One-shot local HTTP listener used to capture the OAuth redirect callback
for desktop sign-in (Google, etc.).

Flow:
  1. server = OAuthCallbackServer(); server.start()
  2. open the provider URL in the browser (page.launch_url)
  3. params = server.wait(timeout)   # blocks until the callback arrives
  4. server.stop()
"""

import http.server
import socketserver
import threading
import urllib.parse

OAUTH_PORT = 8765
REDIRECT_URI = f"http://localhost:{OAUTH_PORT}/callback"

_SUCCESS_HTML = (
    b"<html><body style='font-family:sans-serif;padding:48px;text-align:center'>"
    b"<h2 style='color:#C41E2E'>AyuTech sign-in complete</h2>"
    b"<p>You can close this tab and return to the app.</p>"
    b"</body></html>"
)


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.server.captured = params
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        try:
            self.wfile.write(_SUCCESS_HTML)
        except Exception:
            pass
        # Stop serving after the first callback
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass


class OAuthCallbackServer:
    def __init__(self, port: int = OAUTH_PORT):
        self.port = port
        self.captured = None
        self._httpd = None

    def start(self):
        socketserver.TCPServer.allow_reuse_address = True
        self._httpd = socketserver.TCPServer(("127.0.0.1", self.port), _CallbackHandler)
        self._httpd.captured = None
        self._httpd.timeout = 1
        threading.Thread(
            target=self._httpd.serve_forever,
            kwargs={"poll_interval": 0.2},
            daemon=True,
        ).start()

    def wait(self, timeout: int = 180):
        elapsed = 0.0
        while self._httpd.captured is None and elapsed < timeout:
            threading.Event().wait(0.3)
            elapsed += 0.3
        self.captured = self._httpd.captured
        return self.captured

    def stop(self):
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass
