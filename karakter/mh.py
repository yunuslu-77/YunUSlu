"""MakeHuman/MPFB verilerini (kod çalıştırmadan) okuyup Blender'da karakter kuran yükleyici.

Kaynak veriler (CC0 / AGPL varlıklar):
  - mpfb2/src/mpfb/data       : base.obj, şekil hedefleri, iskelet ve ağırlıklar
  - makehuman-py3-assets/base : deri, saç, kıyafet, kaş, kirpik, göz materyalleri
  - makehuman/data/eyes       : göz geometrisi
Koordinatlar: MakeHuman OBJ Y-yukarı ve desimetre; Blender'a Z-yukarı metre olarak çevrilir.
"""
import gzip, json, os, re
import numpy as np

ROOT = os.environ.get("MH_DL", "/tmp/claude-0/-home-user-YunUSlu/352e0303-df63-50e4-a449-73e957124b54/scratchpad/dl")
MPFB = os.path.join(ROOT, "mpfb2/src/mpfb/data")
ASSETS = os.path.join(ROOT, "assets/base")
MHDATA = os.path.join(ROOT, "makehuman/makehuman/data")


# ---------------------------------------------------------------- OBJ
def read_obj(path):
    """v, vt, faces(list of (vidx list, vtidx list, group, material)) döndürür."""
    V, VT, F = [], [], []
    group, mat = None, None
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("v "):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                VT.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("f "):
                vi, ti = [], []
                for tok in line.split()[1:]:
                    p = tok.split("/")
                    vi.append(int(p[0]) - 1)
                    ti.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                F.append((vi, ti, group, mat))
            elif line.startswith("g "):
                group = line.split(maxsplit=1)[1].strip()
            elif line.startswith("usemtl "):
                mat = line.split(maxsplit=1)[1].strip()
    return np.array(V, dtype=np.float64), np.array(VT, dtype=np.float64), F


def to_blender(co):
    """MakeHuman (x, y-up, z-front) desimetre -> Blender (x, y, z-up) metre."""
    co = np.asarray(co)
    return np.stack([co[..., 0], -co[..., 2], co[..., 1]], axis=-1) * 0.1


# ---------------------------------------------------------------- hedefler
_tcache = {}


def read_target(path):
    if path in _tcache:
        return _tcache[path]
    op = gzip.open if path.endswith(".gz") else open
    idx, d = [], []
    with op(path, "rt") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.split()
            idx.append(int(p[0]))
            d.append([float(p[1]), float(p[2]), float(p[3])])
    r = (np.array(idx, dtype=np.int64), np.array(d, dtype=np.float64).reshape(-1, 3))
    _tcache[path] = r
    return r


def apply_target(V, path, w):
    if abs(w) < 1e-6:
        return
    i, d = read_target(path)
    V[i] += d * w


def _part_weights(v, parts):
    """macro.json mantığı: değerin düştüğü aralıkta iki uç arasında doğrusal ağırlık."""
    out = {}
    for p in parts:
        lo, hi = round(p["lowest"] * 2) / 2, round(p["highest"] * 2) / 2
        if p["lowest"] <= v <= p["highest"]:
            t = 0.0 if hi == lo else (v - lo) / (hi - lo)
            t = min(max(t, 0.0), 1.0)
            if p["low"]:
                out[p["low"]] = out.get(p["low"], 0) + (1 - t)
            if p["high"]:
                out[p["high"]] = out.get(p["high"], 0) + t
            break
    return out


def apply_macros(V, gender=1.0, age=0.5, muscle=0.5, weight=0.5, height=0.5,
                 proportions=0.5, race=(1.0, 0.0, 0.0)):
    macro = json.load(open(os.path.join(MPFB, "targets/macrodetails/macro.json")))["macrotargets"]
    G = _part_weights(gender, macro["gender"]["parts"])
    A = _part_weights(age, macro["age"]["parts"])
    M = _part_weights(muscle, macro["muscle"]["parts"])
    W = _part_weights(weight, macro["weight"]["parts"])
    H = _part_weights(height, macro["height"]["parts"])
    P = _part_weights(proportions, macro["proportions"]["parts"])
    R = dict(zip(["caucasian", "african", "asian"], race))
    base = os.path.join(MPFB, "targets/macrodetails")
    for r, rw in R.items():
        for g, gw in G.items():
            for a, aw in A.items():
                apply_target(V, f"{base}/{r}-{g}-{a}.target.gz", rw * gw * aw)
    for g, gw in G.items():
        for a, aw in A.items():
            for m, mw in M.items():
                for w, ww in W.items():
                    k = gw * aw * mw * ww
                    apply_target(V, f"{base}/universal-{g}-{a}-{m}-{w}.target.gz", k)
                    for h, hw in H.items():
                        apply_target(V, f"{base}/height/{g}-{a}-{m}-{w}-{h}.target.gz", k * hw)
                    for p, pw in P.items():
                        apply_target(V, f"{base}/proportions/{g}-{a}-{m}-{w}-{p}.target.gz", k * pw)


def apply_modifier(V, name, value):
    """'chin/chin-jaw-drop' gibi bir isim ve -1..1 değer: decr/incr hedefini uygular."""
    folder, stem = name.split("/")
    base = os.path.join(MPFB, "targets", folder)
    if value >= 0:
        cand = [f"{stem}-incr", f"{stem}-up", f"{stem}-in", f"{stem}"]
    else:
        cand = [f"{stem}-decr", f"{stem}-down", f"{stem}-out"]
    for c in cand:
        p = os.path.join(base, c + ".target.gz")
        if os.path.exists(p):
            apply_target(V, p, abs(value))
            return p
    raise FileNotFoundError(name)


# ---------------------------------------------------------------- mhclo
def read_mhclo(path):
    d = {"dir": os.path.dirname(path), "refs": [], "delete": [], "scale": {}}
    mode = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if not s or s.startswith("#"):
            if mode == "verts" and not s:
                mode = None
            continue
        if s.startswith("verts"):
            mode = "verts"; continue
        if s.startswith("delete_verts"):
            mode = "delete"; continue
        if mode == "verts":
            p = s.split()
            if len(p) == 1:
                d["refs"].append(((int(p[0]), 0, 0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
                continue
            if len(p) >= 9 and re.match(r"^-?\d+$", p[0]):
                d["refs"].append((tuple(int(x) for x in p[:3]), tuple(float(x) for x in p[3:6]),
                                  tuple(float(x) for x in p[6:9])))
                continue
            mode = None
        if mode == "delete":
            toks = s.split()
            if toks and re.match(r"^\d+$", toks[0]):
                i = 0
                while i < len(toks):
                    if i + 2 < len(toks) and toks[i + 1] == "-":
                        d["delete"].extend(range(int(toks[i]), int(toks[i + 2]) + 1)); i += 3
                    else:
                        d["delete"].append(int(toks[i])); i += 1
                continue
            mode = None
        k, _, v = s.partition(" ")
        if k in ("x_scale", "y_scale", "z_scale"):
            a, b, den = v.split()
            d["scale"][k[0]] = (int(a), int(b), float(den))
        elif k in ("obj_file", "material", "name", "z_depth"):
            d[k] = v.strip()
    return d


def fit_proxy(clo, Vbody):
    """Proxy vertex konumları (MakeHuman uzayında) + referans dizileri."""
    idx = np.array([r[0] for r in clo["refs"]])
    w = np.array([r[1] for r in clo["refs"]])
    off = np.array([r[2] for r in clo["refs"]])
    sc = np.ones(3)
    for ax, i in (("x", 0), ("y", 1), ("z", 2)):
        if ax in clo["scale"]:
            a, b, den = clo["scale"][ax]
            sc[i] = abs(Vbody[a, i] - Vbody[b, i]) / den
    P = (Vbody[idx] * w[..., None]).sum(1) + off * sc
    return P, idx, w


def read_mhmat(path):
    m = {}
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        k, _, v = s.partition(" ")
        m[k] = v.strip()
    m["_dir"] = os.path.dirname(path)
    return m


# ---------------------------------------------------------------- iskelet
def joint_positions(V, groups_verts, rig):
    """Rig JSON'daki head/tail konumlarını (MakeHuman uzayında) hesaplar."""
    def pos(spec):
        s = spec["strategy"]
        if s == "CUBE":
            return V[groups_verts[spec["cube_name"]]].mean(0)
        if s in ("MEAN", "VERTEX"):
            return V[spec["vertex_indices"]].mean(0)
        raise ValueError(s)
    return {b: (pos(v["head"]), pos(v["tail"])) for b, v in rig.items()}
