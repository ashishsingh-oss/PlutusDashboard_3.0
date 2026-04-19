#!/usr/bin/env python3
import os
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MAIN = (
    "https://data.testbook.com/api/queries/19005/results.csv"
    "?api_key=F7QgK93zgSzukkgjWVVpxxRldLPZaoCl6UB3szp9"
)
DEFAULT_BOOKMARK = (
    "https://data.testbook.com/api/queries/22277/results.csv"
    "?api_key=rXuWYBsuyGB4MNBYzr8oRewiMxBOac34xG82A6H5"
)


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/.netlify/functions/data"):
            self._proxy_csv(os.environ.get("UPSTREAM_URL", DEFAULT_MAIN).strip())
            return
        if self.path.startswith("/.netlify/functions/bookmarks"):
            self._proxy_csv(os.environ.get("BOOKMARK_UPSTREAM_URL", DEFAULT_BOOKMARK).strip())
            return
        super().do_GET()

    def _proxy_csv(self, upstream):
        if not upstream:
            msg = b"Set UPSTREAM_URL / BOOKMARK_UPSTREAM_URL (or rely on built-in defaults)."
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        sep = "&" if "?" in upstream else "?"
        url = f"{upstream}{sep}_t={int(time.time() * 1000)}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "PythonLocalProxy/1.0"},
            method="GET",
        )
        insecure_context = ssl._create_unverified_context()
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=insecure_context),
        )
        try:
            with opener.open(request, timeout=20) as resp:
                body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=UTF-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as err:
            payload = f"Upstream HTTP error: {err.code}".encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as err:  # noqa: BLE001
            payload = f"Upstream fetch failed: {err}".encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)


def main():
    port = int(os.environ.get("PORT", "8000"))

    def serve_forever(server):
        server.serve_forever()

    v4 = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    threading.Thread(target=serve_forever, args=(v4,), daemon=True).start()

    try:

        class ThreadingHTTPServerV6(ThreadingHTTPServer):
            address_family = socket.AF_INET6

        v6 = ThreadingHTTPServerV6(("::1", port), DashboardHandler)
        threading.Thread(target=serve_forever, args=(v6,), daemon=True).start()
    except OSError as err:
        print(f"Note: IPv6 loopback ::1 not bound ({err}); use http://127.0.0.1:{port} if localhost fails.")

    print(f"Serving dashboard with proxy on port {port} (127.0.0.1 and ::1 when available)")
    print("Open: http://127.0.0.1:{0} or http://localhost:{0}".format(port))
    print("Proxies: /.netlify/functions/data and /.netlify/functions/bookmarks")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
