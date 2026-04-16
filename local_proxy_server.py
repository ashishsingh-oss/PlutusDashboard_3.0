#!/usr/bin/env python3
import os
import ssl
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
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"Serving dashboard with proxy on http://127.0.0.1:{port}")
    print("Proxies: /.netlify/functions/data and /.netlify/functions/bookmarks")
    server.serve_forever()


if __name__ == "__main__":
    main()
