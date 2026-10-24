"""Images: generation (local or API), editing, app icon sets, understanding for text-only models."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

from ..config import get_secret
from ..core.errors import ToolError

ANDROID_ICONS = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
IOS_ICONS = [(20, 2), (20, 3), (29, 2), (29, 3), (40, 2), (40, 3), (60, 2), (60, 3), (76, 1), (76, 2), (83.5, 2),
             (1024, 1)]
WEB_ICONS = [16, 32, 48, 180, 192, 512]


def _pil():
    try:
        from PIL import Image
        return Image
    except ImportError as e:
        raise ToolError("no_pillow", "Pillow is needed for image editing.", "pip install pillow") from e


def generate(prompt: str, out: Path, size: str = "1024x1024", provider: str | None = None) -> tuple[Path, str]:
    """Text → image. Providers: local ComfyUI/diffusers if configured, else OpenAI / Gemini / Stability keys."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    import httpx
    order = [provider] if provider else ["openai", "gemini", "stability"]
    for p in order:
        if p == "openai" and get_secret("OPENAI_API_KEY"):
            r = httpx.post("https://api.openai.com/v1/images/generations", timeout=300,
                           headers={"Authorization": f"Bearer {get_secret('OPENAI_API_KEY')}"},
                           json={"model": "gpt-image-1", "prompt": prompt, "size": size, "n": 1})
            if r.status_code >= 400:
                raise ToolError("image_failed", r.text[:500])
            out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
            return out, "OpenAI gpt-image-1"
        if p == "gemini" and get_secret("GEMINI_API_KEY"):
            r = httpx.post("https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict",
                           timeout=300, headers={"x-goog-api-key": get_secret("GEMINI_API_KEY")},
                           json={"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}})
            if r.status_code >= 400:
                raise ToolError("image_failed", r.text[:500])
            out.write_bytes(base64.b64decode(r.json()["predictions"][0]["bytesBase64Encoded"]))
            return out, "Google Imagen"
        if p == "stability" and get_secret("STABILITY_API_KEY"):
            r = httpx.post("https://api.stability.ai/v2beta/stable-image/generate/core", timeout=300,
                           headers={"Authorization": f"Bearer {get_secret('STABILITY_API_KEY')}", "accept": "image/*"},
                           files={"none": ""}, data={"prompt": prompt, "output_format": "png"})
            if r.status_code >= 400:
                raise ToolError("image_failed", r.text[:500])
            out.write_bytes(r.content)
            return out, "Stability AI"
        if p == "comfyui":
            raise ToolError("comfyui", "Send a workflow to your local ComfyUI (http://127.0.0.1:8188/prompt) "
                            "with media_comfyui; see the media pack.")
    raise ToolError("no_image_model", "No image generator is available.",
                    "Add an OPENAI_API_KEY, GEMINI_API_KEY or STABILITY_API_KEY, or install the GPU media pack; "
                    "for logos, icons and illustrations, draw them with SVG (render_html) - no model needed.")


def edit(src: Path, out: Path, ops: list[dict]) -> Path:
    """ops: resize{w,h}, crop{x,y,w,h}, fit{w,h,bg}, rotate{deg}, grayscale, text{text,x,y,size,color},
    remove_background, upscale{factor}, format via the out extension."""
    Image = _pil()
    from PIL import ImageDraw, ImageFont, ImageOps
    img = Image.open(src)
    notes = []
    for op in ops:
        kind = op.get("op")
        if kind == "resize":
            img = img.resize((int(op["w"]), int(op["h"])), Image.LANCZOS)
        elif kind == "crop":
            img = img.crop((op["x"], op["y"], op["x"] + op["w"], op["y"] + op["h"]))
        elif kind == "fit":
            img = ImageOps.pad(img.convert("RGBA"), (int(op["w"]), int(op["h"])), color=op.get("bg", "#ffffff"))
        elif kind == "rotate":
            img = img.rotate(-float(op["deg"]), expand=True)
        elif kind == "grayscale":
            img = ImageOps.grayscale(img)
        elif kind == "text":
            img = img.convert("RGBA")
            d = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(op.get("size", 48)))
            except OSError:
                font = ImageFont.load_default()
            d.text((op.get("x", 20), op.get("y", 20)), op["text"], fill=op.get("color", "#ffffff"), font=font,
                   stroke_width=2, stroke_fill="#000000")
        elif kind == "remove_background":
            try:
                from rembg import remove
                img = remove(img)
            except ImportError as e:
                raise ToolError("no_rembg", "Background removal needs rembg.", "pip install rembg") from e
        elif kind == "upscale":
            f = float(op.get("factor", 2))
            if shutil.which("realesrgan-ncnn-vulkan"):
                tmp = Path(out).with_suffix(".in.png")
                img.save(tmp)
                subprocess.run(["realesrgan-ncnn-vulkan", "-i", str(tmp), "-o", str(out), "-s", str(int(f))], check=True)
                img = Image.open(out)
                tmp.unlink(missing_ok=True)
            else:
                img = img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
                notes.append("upscaled with LANCZOS (install Real-ESRGAN for AI upscaling)")
        else:
            raise ToolError("bad_op", f"Unknown image operation {kind}.")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(out, pnginfo=_ai_info() if out.suffix.lower() == ".png" else None)
    return out


def _ai_info():
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    info.add_text("Software", "yWorkspace (YunUSlu)")
    info.add_text("Comment", "Created or edited with AI tools")
    return info


def app_icons(src: Path, out_dir: Path, name: str = "app", background: str = "#ffffff") -> list[Path]:
    """One square source image → Android, iOS, web/PWA, Windows .ico and macOS .icns icon sets."""
    Image = _pil()
    img = Image.open(src).convert("RGBA")
    if img.width != img.height:
        from PIL import ImageOps
        side = max(img.size)
        img = ImageOps.pad(img, (side, side), color=(0, 0, 0, 0))
    out_dir = Path(out_dir)
    written: list[Path] = []

    def save(im, p: Path):
        p.parent.mkdir(parents=True, exist_ok=True)
        im.save(p)
        written.append(p)

    for density, px in ANDROID_ICONS.items():
        save(img.resize((px, px), Image.LANCZOS), out_dir / "android" / f"mipmap-{density}" / "ic_launcher.png")
        fg = int(px * 108 / 48)
        canvas = Image.new("RGBA", (fg, fg), (0, 0, 0, 0))
        inner = img.resize((int(fg * 0.62), int(fg * 0.62)), Image.LANCZOS)
        canvas.paste(inner, ((fg - inner.width) // 2, (fg - inner.height) // 2), inner)
        save(canvas, out_dir / "android" / f"mipmap-{density}" / "ic_launcher_foreground.png")
    images = []
    for pt, scale in IOS_ICONS:
        px = int(pt * scale)
        fname = f"icon-{pt}@{scale}x.png".replace(".0@", "@")
        flat = Image.new("RGB", (px, px), background)  # iOS icons must not be transparent
        icon = img.resize((px, px), Image.LANCZOS)
        flat.paste(icon, (0, 0), icon)
        save(flat, out_dir / "ios" / "AppIcon.appiconset" / fname)
        images.append({"size": f"{pt}x{pt}", "scale": f"{scale}x", "filename": fname,
                       "idiom": "ios-marketing" if pt == 1024 else ("ipad" if pt in (76, 83.5) else "iphone")})
    (out_dir / "ios" / "AppIcon.appiconset" / "Contents.json").write_text(
        json.dumps({"images": images, "info": {"version": 1, "author": "yworkspace"}}, indent=2), "utf-8")
    written.append(out_dir / "ios" / "AppIcon.appiconset" / "Contents.json")
    for px in WEB_ICONS:
        save(img.resize((px, px), Image.LANCZOS), out_dir / "web" / f"icon-{px}.png")
    ico = out_dir / "windows" / f"{name}.ico"
    ico.parent.mkdir(parents=True, exist_ok=True)
    img.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    written.append(ico)
    fav = out_dir / "web" / "favicon.ico"
    img.save(fav, sizes=[(16, 16), (32, 32), (48, 48)])
    written.append(fav)
    try:
        icns = out_dir / "macos" / f"{name}.icns"
        icns.parent.mkdir(parents=True, exist_ok=True)
        img.resize((1024, 1024), Image.LANCZOS).save(icns)
        written.append(icns)
    except (OSError, ValueError, KeyError):
        pass
    manifest = {"name": name, "icons": [{"src": f"icon-{px}.png", "sizes": f"{px}x{px}", "type": "image/png"}
                                        for px in (192, 512)]}
    (out_dir / "web" / "manifest.icons.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return written


def describe_basic(path: Path) -> str:
    """What can be said about an image without any model: size, mode, main colours, OCR text if available."""
    Image = _pil()
    img = Image.open(path)
    small = img.convert("RGB").resize((64, 64))
    colors = sorted(small.getcolors(64 * 64), reverse=True)[:5]
    hexes = ", ".join("#{:02x}{:02x}{:02x}".format(*c[1]) for c in colors)
    text = ""
    if shutil.which("tesseract"):
        r = subprocess.run(["tesseract", str(path), "-", "-l", "eng+tur"], capture_output=True, text=True)
        text = r.stdout.strip()
    return f"{img.width}x{img.height} {img.mode}; main colours: {hexes}" + (f"\nText in the image:\n{text}" if text else "")
