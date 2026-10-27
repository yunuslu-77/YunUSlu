"""Cross-platform zip for recipes (the `zip` command is missing on Windows):
python -m yworkspace.factory.zipdir SOURCE_DIR OUT.zip [--prefix NAME]"""

from __future__ import annotations

import fnmatch
import sys
import zipfile
from pathlib import Path

SKIP = (".yw/*", ".git/*", "*.zip", "*.xpi", "__pycache__/*", "*/__pycache__/*")


def zipdir(src: Path, out: Path, prefix: str = "") -> int:
    src, out = Path(src).resolve(), Path(out).resolve()
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            rel = p.relative_to(src).as_posix()
            if p.is_dir() or p == out or any(fnmatch.fnmatch(rel, pat) for pat in SKIP):
                continue
            z.write(p, f"{prefix}/{rel}" if prefix else rel)
            n += 1
    return n


def command(src: str, out: str, prefix: str = "") -> str:
    import shlex
    parts = [shlex.quote(sys.executable), "-m", "yworkspace.factory.zipdir", shlex.quote(src), shlex.quote(out)]
    if prefix:
        parts += ["--prefix", shlex.quote(prefix)]
    return " ".join(parts)


if __name__ == "__main__":
    args = sys.argv[1:]
    pre = ""
    if "--prefix" in args:
        i = args.index("--prefix")
        pre = args[i + 1]
        del args[i:i + 2]
    print(f"zipped {zipdir(Path(args[0]), Path(args[1]), pre)} files into {args[1]}")
