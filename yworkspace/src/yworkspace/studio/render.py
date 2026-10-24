"""Code-made visuals: render HTML/SVG to PNG and record HTML animations with a real browser.
This is the strongest path for text-only models: they write HTML/SVG/CSS, the browser draws it exactly."""

from __future__ import annotations

import html as htmllib
from pathlib import Path

from ..core.errors import ToolError

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;width:{w}px;height:{h}px;overflow:hidden;background:{bg}}}
</style></head><body>{body}</body></html>"""


def _browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ToolError("no_browser", "Playwright is needed to render HTML/SVG.",
                        "pip install playwright && python -m playwright install chromium") from e
    return sync_playwright()


def wrap(body: str, w: int, h: int, bg: str = "#ffffff") -> str:
    if "<html" in body.lower():
        return body
    return PAGE.format(w=w, h=h, bg=bg, body=body)


def html_to_png(html: str, out: Path, w: int = 1280, h: int = 720, bg: str = "#ffffff", scale: float = 1.0) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with _browser() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        page.set_content(wrap(html, w, h, bg), wait_until="networkidle")
        page.screenshot(path=str(out), full_page=False, omit_background=bg == "transparent")
        b.close()
    return out


def record_animation(html: str, out_webm: Path, seconds: float, w: int = 1280, h: int = 720,
                     bg: str = "#ffffff") -> Path:
    """Record an HTML/CSS/JS animation as video (the browser's own recorder)."""
    out_webm = Path(out_webm)
    out_webm.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_webm.parent / ".rec"
    tmp.mkdir(exist_ok=True)
    with _browser() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": w, "height": h}, record_video_dir=str(tmp),
                            record_video_size={"width": w, "height": h})
        page = ctx.new_page()
        page.set_content(wrap(html, w, h, bg), wait_until="load")
        page.wait_for_timeout(int(seconds * 1000))
        video_path = page.video.path()
        ctx.close()
        b.close()
    Path(video_path).replace(out_webm)
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()
    return out_webm


def svg_chart(kind: str, labels: list[str], values: list[float], title: str = "", w: int = 960, h: int = 540,
              color: str = "#2f6fe4", unit: str = "") -> str:
    """Dependency-free bar/line chart as SVG with readable labels."""
    pad_l, pad_r, pad_t, pad_b = 70, 30, 60 if title else 30, 70
    cw, ch = w - pad_l - pad_r, h - pad_t - pad_b
    vmax = max([*values, 0]) or 1
    vmin = min([*values, 0])
    span = (vmax - vmin) or 1

    def y(v):
        return pad_t + ch - (v - vmin) / span * ch

    n = max(1, len(values))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
             f'font-family="system-ui, sans-serif">', f'<rect width="{w}" height="{h}" fill="#fff"/>']
    if title:
        parts.append(f'<text x="{w / 2}" y="36" text-anchor="middle" font-size="24" font-weight="700" '
                     f'fill="#1b2a3a">{htmllib.escape(title)}</text>')
    for i in range(5):
        v = vmin + span * i / 4
        yy = y(v)
        parts.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#e3e9f3"/>')
        parts.append(f'<text x="{pad_l - 10}" y="{yy + 5:.1f}" text-anchor="end" font-size="14" fill="#5d6f86">'
                     f'{v:,.0f}{htmllib.escape(unit)}</text>')
    step = cw / n
    if kind == "line":
        pts = " ".join(f"{pad_l + step * (i + 0.5):.1f},{y(v):.1f}" for i, v in enumerate(values))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3"/>')
        for i, v in enumerate(values):
            parts.append(f'<circle cx="{pad_l + step * (i + 0.5):.1f}" cy="{y(v):.1f}" r="5" fill="{color}"/>')
    else:
        bw = step * 0.62
        for i, v in enumerate(values):
            x0 = pad_l + step * i + (step - bw) / 2
            top, bottom = min(y(v), y(0)), max(y(v), y(0))
            parts.append(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{bottom - top:.1f}" rx="4" '
                         f'fill="{color}"/>')
            parts.append(f'<text x="{x0 + bw / 2:.1f}" y="{top - 8:.1f}" text-anchor="middle" font-size="14" '
                         f'fill="#1b2a3a">{v:,.0f}{htmllib.escape(unit)}</text>')
    for i, lab in enumerate(labels):
        parts.append(f'<text x="{pad_l + step * (i + 0.5):.1f}" y="{h - pad_b + 28}" text-anchor="middle" '
                     f'font-size="15" fill="#1b2a3a">{htmllib.escape(str(lab))}</text>')
    parts.append("</svg>")
    return "".join(parts)


MERMAID = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script></head>
<body style="margin:0;background:#fff"><pre class="mermaid">{code}</pre>
<script>mermaid.initialize({{startOnLoad:true, theme:'default'}});</script></body></html>"""


def diagram_png(code: str, out: Path, w: int = 1280, h: int = 800) -> Path:
    """Mermaid diagram (flowchart, sequence, ER, gantt...) rendered in the browser."""
    return html_to_png(MERMAID.format(code=htmllib.escape(code)), out, w, h)
