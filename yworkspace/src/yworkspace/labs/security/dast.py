"""Light dynamic security checks against the user's OWN running app (local by default).

Never point this at systems you do not own. Non-local targets require explicit confirmation of ownership.
"""

from __future__ import annotations

import re
import urllib.parse

import httpx

from .scanners import Finding

XSS_PROBE = "yw\"'><svg/onload=alert(1)>"
SQL_ERRORS = re.compile(r"(SQL syntax|sqlite3\.OperationalError|psycopg2?\.|PG::SyntaxError|ORA-\d{5}|"
                        r"Unclosed quotation mark|SQLSTATE\[|syntax error at or near)", re.I)


def _get(client: httpx.Client, url: str, **kw):
    try:
        return client.get(url, **kw)
    except httpx.HTTPError:
        return None


def scan_url(base: str, paths: list[str] | None = None) -> list[Finding]:
    base = base.rstrip("/")
    out: list[Finding] = []
    with httpx.Client(timeout=10, follow_redirects=False) as c:
        home = _get(c, base + "/")
        if home is None:
            return [Finding("info", "dast:unreachable", base, 0, "The app did not answer.", "Start it first.")]
        h = {k.lower(): v for k, v in home.headers.items()}
        if "x-content-type-options" not in h:
            out.append(Finding("low", "dast:no-nosniff", base, 0, "X-Content-Type-Options header missing.",
                               "Send X-Content-Type-Options: nosniff."))
        csp = h.get("content-security-policy", "")
        if "frame-ancestors" not in csp and "x-frame-options" not in h:
            out.append(Finding("medium", "dast:clickjacking", base, 0, "The site can be framed by other sites.",
                               "Send Content-Security-Policy: frame-ancestors 'none' (or X-Frame-Options: DENY)."))
        if base.startswith("https://") and "strict-transport-security" not in h:
            out.append(Finding("medium", "dast:no-hsts", base, 0, "HSTS header missing on HTTPS.",
                               "Send Strict-Transport-Security: max-age=31536000."))
        for cookie in home.headers.get_list("set-cookie"):
            low = cookie.lower()
            if any(n in low for n in ("session", "sid", "token", "auth")) and "httponly" not in low:
                out.append(Finding("high", "dast:cookie-not-httponly", base, 0,
                                   f"Session cookie readable by JavaScript: {cookie.split(';')[0][:40]}",
                                   "Set HttpOnly (and Secure, SameSite) on session cookies."))
        for leak in ("/.env", "/.git/config", "/config.json", "/.DS_Store", "/backup.sql"):
            r = _get(c, base + leak)
            if r is not None and r.status_code == 200 and len(r.content) > 0 and (
                    "=" in r.text or "[core]" in r.text or leak.endswith((".sql", ".DS_Store"))):
                out.append(Finding("critical", "dast:file-exposed", base + leak, 0, f"{leak} is publicly downloadable.",
                                   "Do not serve the project folder; serve only the public/static directory."))
        cors = _get(c, base + "/", headers={"Origin": "https://evil.example"})
        if cors is not None and cors.headers.get("access-control-allow-origin") in ("*", "https://evil.example") and \
                cors.headers.get("access-control-allow-credentials") == "true":
            out.append(Finding("high", "dast:cors-any-origin-credentials", base, 0,
                               "Any website can make authenticated requests to this API.",
                               "Allow only your own origins."))
        for p in (paths or ["/", "/login", "/search"]):
            for param in ("next", "redirect", "url", "return_to"):
                r = _get(c, f"{base}{p}?{param}=//evil.example")
                loc = r.headers.get("location", "") if r is not None else ""
                if loc.startswith(("//evil.example", "https://evil.example", "http://evil.example")):
                    out.append(Finding("medium", "dast:open-redirect", f"{base}{p}?{param}=", 0,
                                       "Redirects to any external site.", "Only allow relative paths starting with a single /."))
            for param in ("q", "search", "name", "msg", "error"):
                r = _get(c, f"{base}{p}?{param}={urllib.parse.quote(XSS_PROBE)}")
                if r is not None and XSS_PROBE in r.text:
                    out.append(Finding("high", "dast:reflected-xss", f"{base}{p}?{param}=", 0,
                                       "Input is reflected into the page without escaping.",
                                       "Escape output (template autoescape) and validate input."))
                r = _get(c, f"{base}{p}?{param}=1'\"")
                if r is not None and SQL_ERRORS.search(r.text or ""):
                    out.append(Finding("critical", "dast:sql-error", f"{base}{p}?{param}=", 0,
                                       "A quote in the input causes a database error: likely SQL injection.",
                                       "Use parameterized queries; never show database errors to users."))
    return out
