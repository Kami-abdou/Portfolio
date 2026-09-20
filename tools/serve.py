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

So this adds the single rule Pages applies: if the path has no extension
and <path>.html exists, serve that. Everything else is left alone.

Responses are also marked no-store. The build fingerprints CSS and JS with
a content hash, but the HTML itself has no version in its URL, so a cached
copy of a page will happily keep pointing at assets that have been rebuilt.
"""
import http.server
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8123


class PagesHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        full = super().translate_path(path)
        # Only for extensionless paths that are not an existing directory,
        # so /assets/, /projects/ and real files keep their normal handling.
        if not os.path.splitext(full)[1] and not os.path.isdir(full):
            if os.path.isfile(full + ".html"):
                return full + ".html"
        return full

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))


if __name__ == "__main__":
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), PagesHandler) as httpd:
        print("serving %s at http://localhost:%d" % (ROOT, PORT))
        print("extensionless URLs resolve to .html, as on GitHub Pages")
        httpd.serve_forever()
