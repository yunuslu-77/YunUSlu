"""3D: code-made models (OpenSCAD for printable parts, Blender scripts, Three.js scenes) and a pure-Python STL
writer for simple solids, so even text-only models can produce printable files."""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

from ..core.errors import ToolError


def openscad(code: str, out: Path) -> Path:
    if not shutil.which("openscad"):
        raise ToolError("no_openscad", "OpenSCAD is not installed.", "Install OpenSCAD for printable parts.")
    src = Path(out).with_suffix(".scad")
    src.write_text(code, "utf-8")
    r = subprocess.run(["openscad", "-o", str(out), str(src)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise ToolError("openscad_failed", r.stderr[-1500:])
    return Path(out)


def blender(script: str, out: Path) -> Path:
    if not shutil.which("blender"):
        raise ToolError("no_blender", "Blender is not installed.")
    src = Path(out).with_suffix(".py")
    src.write_text(script + f"\nimport bpy\nbpy.ops.export_scene.gltf(filepath={str(out)!r})\n", "utf-8")
    r = subprocess.run(["blender", "--background", "--python", str(src)], capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not Path(out).exists():
        raise ToolError("blender_failed", (r.stdout + r.stderr)[-1500:])
    return Path(out)


def box_stl(w: float, d: float, h: float, out: Path) -> Path:
    """A rectangular block as binary STL (mm)."""
    v = [(0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0), (0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    data = bytearray(b"yWorkspace STL".ljust(80, b" ")) + struct.pack("<I", len(faces))
    for a, b, c in faces:
        p, q, r = v[a], v[b], v[c]
        u = [q[i] - p[i] for i in range(3)]
        s = [r[i] - p[i] for i in range(3)]
        n = (u[1] * s[2] - u[2] * s[1], u[2] * s[0] - u[0] * s[2], u[0] * s[1] - u[1] * s[0])
        ln = sum(x * x for x in n) ** 0.5 or 1
        data += struct.pack("<3f", *(x / ln for x in n)) + struct.pack("<9f", *p, *q, *r) + b"\x00\x00"
    Path(out).write_bytes(bytes(data))
    return Path(out)


def stl_triangles(path: Path) -> int:
    data = Path(path).read_bytes()
    return struct.unpack("<I", data[80:84])[0]
