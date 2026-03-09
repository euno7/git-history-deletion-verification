"""Tiny stdlib-only JSON API used as dummy content."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from app import handlers

ROUTES = {}


def route(path):
    def deco(fn):
        ROUTES[path] = fn
        return fn
    return deco


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        fn = ROUTES.get(self.path) or getattr(handlers, "ROUTES", {}).get(self.path)
        if fn is None:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(fn()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


@route("/health")
def health():
    return {"status": "ok"}


def main(port=8080):
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
