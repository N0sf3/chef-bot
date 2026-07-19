"""
web.py — the recipe-page server. One job: serve GET /r/<slug> as a tiny public
page carrying schema.org/Recipe JSON-LD, which MyFitnessPal's "Copy from the
Web" importer can scrape. Runs as a daemon thread beside the Telegram poller.

Privacy model: pages must be public (MFP's scraper has no auth), so the slug
IS the secret — random, unguessable, never listed anywhere.
"""

import html
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import db

_SLUG_RE = re.compile(r"^/r/([A-Za-z0-9_-]{6,32})/?$")

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
<script type="application/ld+json">{jsonld}</script>
<style>
  body {{ background:#0b0714; color:#f2ead8; font-family: Georgia, serif;
         max-width: 42em; margin: 0 auto; padding: 2em 1.2em; line-height: 1.6; }}
  h1 {{ font-style: italic; font-weight: 400; color:#c4b0ff; }}
  h2 {{ font-size: 1em; letter-spacing: .2em; text-transform: uppercase;
        color:#aeeed3; margin-top: 2em; }}
  li {{ margin: .3em 0; }}
  .meta {{ color:#a89bb8; font-size: .9em; }}
  footer {{ margin-top: 3em; color:#a89bb8; font-size: .8em; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">{yield_} · {calories}</p>
<h2>Ingredients</h2>
<ul>{ingredients}</ul>
<h2>Steps</h2>
<ol>{steps}</ol>
<footer>cooked by the Dissident Labs chef 🔪</footer>
</body>
</html>"""


def _render(structured: str) -> bytes | None:
    """Build the page from the stored RECIPE_JSON string. None if unusable."""
    try:
        data = json.loads(structured)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not data.get("name"):
        return None
    jsonld = {"@context": "https://schema.org", "@type": "Recipe", **data}
    nutrition = data.get("nutrition") or {}
    if isinstance(nutrition, dict) and nutrition:
        jsonld["nutrition"] = {"@type": "NutritionInformation", **nutrition}
    ingredients = data.get("recipeIngredient") or []
    steps = data.get("recipeInstructions") or []
    page = _PAGE.format(
        title=html.escape(str(data.get("name"))),
        jsonld=json.dumps(jsonld, ensure_ascii=False),
        yield_=html.escape(str(data.get("recipeYield", ""))),
        calories=html.escape(str(nutrition.get("calories", "") if isinstance(nutrition, dict) else "")),
        ingredients="".join(f"<li>{html.escape(str(i))}</li>" for i in ingredients),
        steps="".join(f"<li>{html.escape(str(s))}</li>" for s in steps),
    )
    return page.encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path in ("/", "/health"):
            self._send(200, b"ok", "text/plain; charset=utf-8")
            return
        m = _SLUG_RE.match(self.path)
        row = db.recipe_by_slug(m.group(1)) if m else None
        body = _render(row["structured"]) if row and row["structured"] else None
        if body is None:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        self._send(200, body, "text/html; charset=utf-8")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the poller's stdout clean
        pass


def start(port: int) -> None:
    """Serve forever on a daemon thread — dies with the bot, never blocks it."""
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Recipe pages serving on :{port}")
