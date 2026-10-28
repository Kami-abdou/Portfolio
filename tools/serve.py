#!/usr/bin/env python3
"""Local preview server that resolves URLs the way GitHub Pages does.

    python3 tools/serve.py [port]

Why this exists rather than `python3 -m http.server`:

The site's internal links are extensionless -- /work, /about, /contact.
GitHub Pages serves any foo.html at /foo, so those resolve in production.
SimpleHTTPRequestHandler does not: it looks for a file called exactly
"work", finds nothing, and returns 404. Previewing with the stock server
therefore 404s on every page in the nav while the deployed site is fine,
which is the worst possible split -- local testing that disagrees with
production on the one thing you just changed.

So this adds the two rules Pages applies: if the path has no extension
and <path>.html exists, serve that; and if nothing matches at all, serve
/404.html with a 404 status. Everything else is left alone.

The second rule exists for the same reason as the first. Without it a
missing page here shows Python's "Error response / HTTPStatus.NOT_FOUND"
and on the deployed site it shows the site's own 404 -- so the one page
you can only reach by making a mistake is the one page local preview
never showed you.

Responses are also marked no-store. The build fingerprints CSS and JS with
a content hash, but the HTML itself has no version in its URL, so a cached
copy of a page will happily keep pointing at assets that have been rebuilt.
"""
import http.server
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PORT = int(ARGS[0]) if ARGS else 8123

# --lan binds to every interface so a phone on the same wifi can reach it.
# Localhost-only is the right default -- this serves an unfinished site off
# a laptop -- but the one thing you cannot check from the laptop is the one
# thing that only happens without a cursor: the index covers appear under
# `(hover: none)`, and a desktop browser's device emulator still reports a
# fine pointer. A real phone is the only honest test.
HOST = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"


class PagesHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        full = super().translate_path(path)
        # Only for extensionless paths that are not an existing directory,
        # so /assets/, /projects/ and real files keep their normal handling.
        if not os.path.splitext(full)[1] and not os.path.isdir(full):
            if os.path.isfile(full + ".html"):
                return full + ".html"
        return full

    def send_error(self, code, message=None, explain=None):
        """Serve the site's own 404, as Pages does.

        Only for 404 on a GET: a HEAD must not carry a body, and
        anything else (403, 501) is a different failure that this page
        would misdescribe.

        send_response_only + the headers by hand, rather than
        send_response, because the latter logs a second time and this
        request has already been logged.
        """
        page = os.path.join(ROOT, "404.html")
        if code != 404 or self.command != "GET" or not os.path.isfile(page):
            return super().send_error(code, message, explain)
        body = open(page, "rb").read()
        self.send_response_only(404, message)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))


if __name__ == "__main__":
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), PagesHandler) as httpd:
        print("serving %s at http://localhost:%d" % (ROOT, PORT))
        if HOST != "127.0.0.1":
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(("8.8.8.8", 80))
                print("on this wifi:  http://%s:%d" % (sock.getsockname()[0], PORT))
            except OSError:
                pass
            finally:
                sock.close()
        print("extensionless URLs resolve to .html, and misses get "
              "404.html -- as on GitHub Pages")
        httpd.serve_forever()
