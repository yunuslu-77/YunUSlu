"""A small, dependency-free QR code encoder (byte mode, error correction level M, versions 1-10).
Enough for pairing links; output as SVG, PNG (Pillow) or terminal text."""

from __future__ import annotations

# version: (ec codewords per block, [(block count, data codewords per block), ...])  - level M
EC_M = {1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
        6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
        10: (26, [(4, 43), (1, 44)])}
ALIGN = {2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
         9: [6, 26, 46], 10: [6, 28, 50]}
REMAINDER = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}

EXP = [0] * 512
LOG = [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def _rs_ec(data: list[int], n: int) -> list[int]:
    gen = [1]
    for i in range(n):
        nxt = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            nxt[j] ^= g
            nxt[j + 1] ^= _mul(g, EXP[i])
        gen = nxt
    rem = [0] * n
    for d in data:
        factor = d ^ rem[0]
        rem = rem[1:] + [0]
        for j in range(n):
            rem[j] ^= _mul(gen[j + 1], factor)
    return rem


def _codewords(payload: bytes) -> tuple[int, list[int]]:
    for version in range(1, 11):
        ec, blocks = EC_M[version]
        capacity = sum(c * d for c, d in blocks)
        count_bits = 8 if version < 10 else 16
        if 4 + count_bits + 8 * len(payload) <= capacity * 8:
            break
    else:
        raise ValueError("text too long for a version-10 QR code (max ~213 bytes)")
    bits = [0, 1, 0, 0] + [(len(payload) >> i) & 1 for i in range(count_bits - 1, -1, -1)]
    for b in payload:
        bits += [(b >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, capacity * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0
    while len(data) < capacity:
        data.append((0xEC, 0x11)[pad % 2])
        pad += 1
    groups, i = [], 0
    for count, size in blocks:
        for _ in range(count):
            groups.append(data[i:i + size])
            i += size
    ecs = [_rs_ec(g, ec) for g in groups]
    out = []
    for k in range(max(len(g) for g in groups)):
        out += [g[k] for g in groups if k < len(g)]
    for k in range(ec):
        out += [e[k] for e in ecs]
    return version, out


def _penalty(m: list[list[bool]]) -> int:
    n = len(m)
    score = 0
    for grid in (m, [list(r) for r in zip(*m, strict=True)]):
        for row in grid:
            run, prev = 0, None
            for v in row:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run, prev = 1, v
            if run >= 5:
                score += run - 2
            s = "".join("1" if v else "0" for v in row)
            score += 40 * (s.count("1011101" + "0000") + s.count("0000" + "1011101"))
    for y in range(n - 1):
        for x in range(n - 1):
            if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                score += 3
    dark = sum(map(sum, m))
    score += abs(dark * 20 - n * n * 10) // (n * n) * 10
    return score


MASKS = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
         lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
         lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
         lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]


def encode(text: str) -> list[list[bool]]:
    """Returns the module matrix (True = dark), without the quiet zone."""
    version, words = _codewords(text.encode("utf-8"))
    n = version * 4 + 17
    mod = [[False] * n for _ in range(n)]
    fn = [[False] * n for _ in range(n)]

    def put(x, y, dark):
        mod[y][x] = dark
        fn[y][x] = True

    for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < n and 0 <= y < n:
                    d = max(abs(dx), abs(dy))
                    put(x, y, d not in (2, 4))
    for i in range(n):
        if not fn[6][i]:
            put(i, 6, i % 2 == 0)
        if not fn[i][6]:
            put(6, i, i % 2 == 0)
    pos = ALIGN.get(version, [])
    for ay in pos:
        for ax in pos:
            if (ax == 6 and ay == 6) or (ax == 6 and ay == pos[-1]) or (ax == pos[-1] and ay == 6):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    put(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
    # reserve format areas (filled later) and the dark module
    for i in range(9):
        fn[8][i] = fn[i][8] = True
    for i in range(8):
        fn[8][n - 1 - i] = fn[n - 1 - i][8] = True
    put(8, n - 8, True)
    if version >= 7:
        rem = version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = version << 12 | rem
        for i in range(18):
            bit = (bits >> i) & 1 == 1
            a, b = n - 11 + i % 3, i // 3
            put(a, b, bit)
            put(b, a, bit)
    # data, zigzag
    i, total = 0, len(words) * 8 + REMAINDER[version]
    right = n - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(n):
            for j in range(2):
                x = right - j
                upward = ((right + 1) & 2) == 0
                y = n - 1 - vert if upward else vert
                if not fn[y][x] and i < total:
                    if i < len(words) * 8:
                        mod[y][x] = (words[i >> 3] >> (7 - (i & 7))) & 1 == 1
                    i += 1
        right -= 2

    def with_mask(k):
        m = [row[:] for row in mod]
        for y in range(n):
            for x in range(n):
                if not fn[y][x] and MASKS[k](x, y):
                    m[y][x] = not m[y][x]
        data = (0b00 << 3) | k  # level M = 00
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = ((data << 10) | rem) ^ 0x5412

        def setf(x, y, b):
            m[y][x] = (bits >> b) & 1 == 1
        for b in range(6):
            setf(8, b, b)
        setf(8, 7, 6)
        setf(8, 8, 7)
        setf(7, 8, 8)
        for b in range(9, 15):
            setf(14 - b, 8, b)
        for b in range(8):
            setf(n - 1 - b, 8, b)
        for b in range(8, 15):
            setf(8, n - 15 + b, b)
        m[n - 8][8] = True
        return m

    return min((with_mask(k) for k in range(8)), key=_penalty)


def svg(text: str, scale: int = 8, border: int = 4, dark: str = "#000", light: str = "#fff") -> str:
    m = encode(text)
    n = len(m) + 2 * border
    path = "".join(f"M{x + border},{y + border}h1v1h-1z" for y, row in enumerate(m) for x, v in enumerate(row) if v)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n * scale}" height="{n * scale}" '
            f'shape-rendering="crispEdges"><rect width="{n}" height="{n}" fill="{light}"/>'
            f'<path d="{path}" fill="{dark}"/></svg>')


def png(text: str, path, scale: int = 8, border: int = 4):
    from PIL import Image
    m = encode(text)
    n = len(m) + 2 * border
    img = Image.new("L", (n, n), 255)
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                img.putpixel((x + border, y + border), 0)
    img.resize((n * scale, n * scale), Image.NEAREST).save(path)
    return path


def terminal(text: str) -> str:
    """Two rows per character with half blocks, so it scans from a terminal window."""
    m = encode(text)
    b = 2
    n = len(m)
    grid = [[False] * (n + 2 * b) for _ in range(b)] + [[False] * b + r + [False] * b for r in m] + \
        [[False] * (n + 2 * b) for _ in range(b + 1)]
    lines = []
    for y in range(0, len(grid) - 1, 2):
        top, bot = grid[y], grid[y + 1]
        lines.append("".join(" " if not t and not u else "▀" if t and not u else "▄" if u and not t else "█"
                             for t, u in zip(top, bot, strict=True)).translate(str.maketrans("▀▄█ ", "▄▀ █")))
    return "\n".join(lines)
