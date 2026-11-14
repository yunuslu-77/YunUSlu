"""Karakteri kurar ve karakter.blend olarak kaydeder.

Çalıştırma:  python3 karakter/build.py <çıktı.blend>
"""
import json, math, os, sys
import numpy as np
import bpy, bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import mh, groom

OUT = sys.argv[1] if len(sys.argv) > 1 else "karakter.blend"
A, MP = mh.ASSETS, mh.MPFB

# ------------------------------------------------------------ karakter ayarları
MACROS = dict(gender=1.0, age=0.53, muscle=0.78, weight=0.42, height=0.52,
              proportions=0.95, race=(0.80, 0.12, 0.08))
SHAPE = [  # (hedef dosyası, ağırlık): güçlü çene, belirgin elmacık, V gövde
    ("head/head-square", 0.35), ("head/head-oval", 0.25),
    ("chin/chin-width-incr", 0.25), ("chin/chin-bones-incr", 0.45),
    ("chin/chin-prominent-incr", 0.25), ("chin/chin-height-decr", 0.1),
    ("cheek/l-cheek-bones-incr", 0.35), ("cheek/r-cheek-bones-incr", 0.35),
    ("cheek/l-cheek-volume-decr", 0.3), ("cheek/r-cheek-volume-decr", 0.3),
    ("eyebrows/eyebrows-trans-down", 0.25), ("eyebrows/eyebrows-angle-down", 0.2),
    ("eyes/l-eye-height2-decr", 0.2), ("eyes/r-eye-height2-decr", 0.2),
    ("nose/nose-scale-horiz-decr", 0.1), ("nose/nose-hump-incr", 0.15),
    ("mouth/mouth-scale-horiz-incr", 0.1),
    ("neck/neck-scale-horiz-incr", 0.35), ("neck/neck-scale-depth-incr", 0.2),
    ("torso/torso-vshape-incr", 0.55), ("torso/measure-shoulder-dist-incr", 0.25),
    ("torso/measure-waist-circ-decr", 0.35), ("torso/torso-muscle-pectoral-incr", 0.3),
    ("torso/torso-muscle-dorsi-incr", 0.4),
]
CLOTHES = ["clothes/male_casualsuit05/male_casualsuit05.mhclo",
           "clothes/shoes03/shoes03.mhclo"]
HAIR = "hair/short02/short02.mhclo"
BROWS = "eyebrows/eyebrow009/eyebrow009.mhclo"
LASHES = "eyelashes/eyelashes01/eyelashes01.mhclo"
EYES = os.path.join(mh.MHDATA, "eyes/high-poly/high-poly.mhclo")
EYE_TEX = os.path.join(A, "eyes/materials/brownlight_eye.png")
RIG = "cmu_mb"


# ------------------------------------------------------------ yardımcılar
def img(path, noncolor=False):
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        im.colorspace_settings.name = "Non-Color"
    return im


def new_mesh(name, V, faces, uv_faces=None, VT=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [tuple(f) for f in faces])
    if uv_faces is not None and VT is not None and len(VT):
        uv = me.uv_layers.new(name="UVMap")
        flat = [VT[t] for tf in uv_faces for t in tf]
        uv.data.foreach_set("uv", np.array(flat, dtype=np.float32).ravel())
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def add_weights(ob, Wmat, bones, thresh=1e-3):
    for j, b in enumerate(bones):
        col = Wmat[:, j]
        nz = np.nonzero(col > thresh)[0]
        if len(nz) == 0:
            continue
        vg = ob.vertex_groups.new(name=b)
        for i in nz:
            vg.add([int(i)], float(col[i]), "REPLACE")


def principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def tex_node(nt, image, x=-700, y=0):
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = image; t.location = (x, y)
    return t


def normal_map(nt, bsdf, image, strength=1.0):
    t = tex_node(nt, image, -700, -400)
    n = nt.nodes.new("ShaderNodeNormalMap"); n.location = (-350, -400); n.inputs["Strength"].default_value = strength
    nt.links.new(t.outputs["Color"], n.inputs["Color"])
    nt.links.new(n.outputs["Normal"], bsdf.inputs["Normal"])


# ------------------------------------------------------------ sahne temizle
bpy.ops.wm.read_factory_settings(use_empty=True)

# ------------------------------------------------------------ gövde
V0, VT, F = mh.read_obj(os.path.join(MP, "3dobjs/base.obj"))
V = V0.copy()
mh.apply_macros(V, **MACROS)
for t, w in SHAPE:
    mh.apply_target(V, os.path.join(MP, "targets", t + ".target.gz"), w)

groups = {}
for vi, ti, g, m in F:
    groups.setdefault(g, set()).update(vi)
groups = {g: np.array(sorted(s)) for g, s in groups.items()}

# kıyafetler (altında kalan deriyi silmek için önce oku)
clo_data = [mh.read_mhclo(os.path.join(A, c)) for c in CLOTHES]
deleted = set()
for c in clo_data:
    deleted.update(c["delete"])

# iskelet ağırlıkları (tam vertex listesi üzerinde)
rig = json.load(open(os.path.join(MP, f"rigs/standard/rig.{RIG}.json")))
wts = json.load(open(os.path.join(MP, f"rigs/standard/weights.{RIG}.json")))["weights"]
bones = list(rig.keys())
Wb = np.zeros((len(V), len(bones)))
for j, b in enumerate(bones):
    for i, w in wts.get(b, []):
        Wb[i, j] = w
s = Wb.sum(1, keepdims=True); s[s == 0] = 1; Wb /= s

BV = mh.to_blender(V)
ground = BV[groups["body"]][:, 2].min()
BV[:, 2] -= ground

body_faces = [(vi, ti) for vi, ti, g, m in F if g == "body" and not (set(vi) & deleted)]
body = new_mesh("Govde", BV, [f[0] for f in body_faces], [f[1] for f in body_faces], VT)
add_weights(body, Wb, bones)
att = body.data.attributes.new("orig_index", "INT", "POINT")
att.data.foreach_set("value", np.arange(len(BV), dtype=np.int32))
# kullanılmayan (helper/joint) vertexleri sil — vertex grupları korunur
bm = bmesh.new(); bm.from_mesh(body.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(body.data); bm.free()
orig_index = np.zeros(len(body.data.vertices), dtype=np.int32)
body.data.attributes["orig_index"].data.foreach_get("value", orig_index)


# ------------------------------------------------------------ proxy nesneleri
def build_proxy(path, name):
    c = mh.read_mhclo(path) if isinstance(path, str) else path
    P, idx, w = mh.fit_proxy(c, V)
    PV, PT, PF = mh.read_obj(os.path.join(c["dir"], c["obj_file"]))
    PB = mh.to_blender(P); PB[:, 2] -= ground
    ob = new_mesh(name, PB, [f[0] for f in PF], [f[1] for f in PF], PT)
    Wp = (Wb[idx] * w[..., None]).sum(1)
    s = Wp.sum(1, keepdims=True); s[s == 0] = 1
    add_weights(ob, Wp / s, bones)
    mat = mh.read_mhmat(os.path.join(c["dir"], c["material"])) if c.get("material") else {}
    return ob, mat


def std_material(name, mat, alpha=False, tint=None, rough=0.7, sheen=0.0):
    m, nt, b = principled(name)
    b.inputs["Roughness"].default_value = rough
    if "diffuseTexture" in mat:
        t = tex_node(nt, img(os.path.join(mat["_dir"], mat["diffuseTexture"])))
        col = t.outputs["Color"]
        if tint is not None:
            hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.location = (-400, 150)
            hs.inputs["Hue"].default_value, hs.inputs["Saturation"].default_value, hs.inputs["Value"].default_value = tint
            nt.links.new(col, hs.inputs["Color"]); col = hs.outputs["Color"]
        nt.links.new(col, b.inputs["Base Color"])
        if alpha:
            nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
    if "normalmapTexture" in mat:
        normal_map(nt, b, img(os.path.join(mat["_dir"], mat["normalmapTexture"]), True), 1.0)
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    return m


objs = [body]
TEX = os.environ.get("KIYAFET_TEX", os.path.join(os.path.dirname(os.path.abspath(OUT)), "tex"))
ob, mat = build_proxy(clo_data[0], "Kiyafet")
m, nt, b = principled("Kiyafet")
t = tex_node(nt, img(os.path.join(TEX, "kiyafet_diffuse.png"))); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
b.inputs["Coat Weight"].default_value = 0.0
r = tex_node(nt, img(os.path.join(TEX, "kiyafet_rough.png"), True), -700, -200); nt.links.new(r.outputs["Color"], b.inputs["Roughness"])
normal_map(nt, b, img(os.path.join(mat["_dir"], mat["normalmapTexture"]), True), 1.2)
b.inputs["Specular IOR Level"].default_value = 0.35
ob.data.materials.append(m); objs.append(ob)
ob, mat = build_proxy(clo_data[1], "Ayakkabi")
ob.data.materials.append(std_material("Ayakkabi", mat, rough=0.3)); objs.append(ob)

hair_clo = mh.read_mhclo(os.path.join(A, HAIR))
ob, mat = build_proxy(hair_clo, "Sac_Kart")  # oyun motoru için kart saç (render'da gizli)
ob.data.materials.append(std_material("Sac_Kart", mat, alpha=True, tint=(0.5, 1.1, 0.3), rough=0.5))
ob.hide_render = True
objs.append(ob)
for path, name in ((os.path.join(A, BROWS), "Kas"), (os.path.join(A, LASHES), "Kirpik")):
    ob, mat = build_proxy(path, name)
    ob.data.materials.append(std_material(name, mat, alpha=True, tint=(0.5, 0.5, 0.12), rough=0.6))
    objs.append(ob)

eyes, _ = build_proxy(EYES, "Gozler")
m, nt, b = principled("Goz")
t = tex_node(nt, img(EYE_TEX))
ehs = nt.nodes.new("ShaderNodeHueSaturation"); ehs.location = (-350, 200)
ehs.inputs["Hue"].default_value = 0.5; ehs.inputs["Saturation"].default_value = 1.2; ehs.inputs["Value"].default_value = 0.6
nt.links.new(t.outputs["Color"], ehs.inputs["Color"]); nt.links.new(ehs.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.25
b.inputs["Subsurface Weight"].default_value = 0.1
glass = nt.nodes.new("ShaderNodeBsdfPrincipled"); glass.location = (0, -500)
glass.inputs["Transmission Weight"].default_value = 1.0
glass.inputs["Roughness"].default_value = 0.0
glass.inputs["IOR"].default_value = 1.376
mixs = nt.nodes.new("ShaderNodeMixShader"); mixs.location = (300, 0)
out = nt.nodes["Material Output"]
nt.links.new(t.outputs["Alpha"], mixs.inputs["Fac"])
nt.links.new(glass.outputs["BSDF"], mixs.inputs[1]); nt.links.new(b.outputs["BSDF"], mixs.inputs[2])
nt.links.new(mixs.outputs["Shader"], out.inputs["Surface"])
eyes.data.materials.append(m)
objs.append(eyes)

# ------------------------------------------------------------ deri materyali
m, nt, b = principled("Deri")
light = tex_node(nt, img(os.path.join(A, "skins/textures/young_lightskinned_male_diffuse.png")), -1100, 200)
dark = tex_node(nt, img(os.path.join(A, "skins/textures/young_darkskinned_male_diffuse.png")), -1100, -100)
mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.location = (-750, 100)
mix.inputs["Factor"].default_value = 0.55
nt.links.new(light.outputs["Color"], mix.inputs["A"]); nt.links.new(dark.outputs["Color"], mix.inputs["B"])
hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.location = (-500, 100)
hs.inputs["Hue"].default_value = 0.495; hs.inputs["Saturation"].default_value = 0.92; hs.inputs["Value"].default_value = 0.9
nt.links.new(mix.outputs["Result"], hs.inputs["Color"])
tan = nt.nodes.new("ShaderNodeMix"); tan.data_type = "RGBA"; tan.blend_type = "MULTIPLY"; tan.location = (-300, 100)
tan.inputs["Factor"].default_value = 1.0; tan.inputs["B"].default_value = (0.86, 0.68, 0.52, 1.0)  # Akdeniz bronz tonu
nt.links.new(hs.outputs["Color"], tan.inputs["A"])
# hafif renk dalgalanması (kızarıklık/ton farkları)
mott = nt.nodes.new("ShaderNodeTexNoise"); mott.location = (-700, 500); mott.inputs["Scale"].default_value = 45.0
mott.inputs["Detail"].default_value = 4.0
tcm = nt.nodes.new("ShaderNodeTexCoord"); tcm.location = (-950, 500)
nt.links.new(tcm.outputs["Object"], mott.inputs["Vector"])
red = nt.nodes.new("ShaderNodeMix"); red.data_type = "RGBA"; red.blend_type = "OVERLAY"; red.location = (-100, 300)
red.inputs["Factor"].default_value = 0.12
nt.links.new(tan.outputs["Result"], red.inputs["A"]); nt.links.new(mott.outputs["Color"], red.inputs["B"])
# saç ve sakal altı koyulaşma
amask = nt.nodes.new("ShaderNodeAttribute"); amask.attribute_name = "sac_maske"; amask.location = (-100, 600)
bmask = nt.nodes.new("ShaderNodeAttribute"); bmask.attribute_name = "sakal_maske"; bmask.location = (-100, 750)
sm = nt.nodes.new("ShaderNodeMath"); sm.operation = "MULTIPLY"; sm.inputs[1].default_value = 0.85; sm.location = (80, 600)
nt.links.new(amask.outputs["Fac"], sm.inputs[0])
scalp_mix = nt.nodes.new("ShaderNodeMix"); scalp_mix.data_type = "RGBA"; scalp_mix.location = (250, 400)
scalp_mix.inputs["B"].default_value = (0.03, 0.022, 0.018, 1)
nt.links.new(sm.outputs["Value"], scalp_mix.inputs["Factor"]); nt.links.new(red.outputs["Result"], scalp_mix.inputs["A"])
bm_ = nt.nodes.new("ShaderNodeMath"); bm_.operation = "MULTIPLY"; bm_.inputs[1].default_value = 0.55; bm_.location = (80, 750)
nt.links.new(bmask.outputs["Fac"], bm_.inputs[0])
beard_mix = nt.nodes.new("ShaderNodeMix"); beard_mix.data_type = "RGBA"; beard_mix.location = (420, 400)
beard_mix.inputs["B"].default_value = (0.11, 0.095, 0.095, 1)  # tıraş gölgesi: gri-mavimsi
nt.links.new(bm_.outputs["Value"], beard_mix.inputs["Factor"]); nt.links.new(scalp_mix.outputs["Result"], beard_mix.inputs["A"])
nt.links.new(beard_mix.outputs["Result"], b.inputs["Base Color"])
# pürüzlülük farkı (alın/burun daha yağlı)
rn = nt.nodes.new("ShaderNodeTexNoise"); rn.location = (-700, -250); rn.inputs["Scale"].default_value = 30.0
nt.links.new(tcm.outputs["Object"], rn.inputs["Vector"])
rmr = nt.nodes.new("ShaderNodeMapRange"); rmr.location = (-450, -250)
rmr.inputs["To Min"].default_value = 0.4; rmr.inputs["To Max"].default_value = 0.58
nt.links.new(rn.outputs["Fac"], rmr.inputs["Value"]); nt.links.new(rmr.outputs["Result"], b.inputs["Roughness"])
b.inputs["Subsurface Weight"].default_value = 0.3
b.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
b.inputs["Subsurface Scale"].default_value = 0.006
b.inputs["Roughness"].default_value = 0.48
b.inputs["Specular IOR Level"].default_value = 0.45
# gözenek / mikro detay
tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1300, -500)
nz = nt.nodes.new("ShaderNodeTexNoise"); nz.location = (-1000, -500)
nz.inputs["Scale"].default_value = 1200.0; nz.inputs["Detail"].default_value = 8.0
vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.location = (-1000, -750); vo.inputs["Scale"].default_value = 2600.0
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"]); nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MULTIPLY"; mx.location = (-750, -600)
nt.links.new(nz.outputs["Fac"], mx.inputs[0]); nt.links.new(vo.outputs["Distance"], mx.inputs[1])
bump = nt.nodes.new("ShaderNodeBump"); bump.location = (-400, -500)
bump.inputs["Strength"].default_value = 0.22; bump.inputs["Distance"].default_value = 0.0004
nt.links.new(mx.outputs["Value"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
body.data.materials.append(m)

# ------------------------------------------------------------ iskelet
J = mh.joint_positions(V, groups, rig)
arm_data = bpy.data.armatures.new("Iskelet")
arm = bpy.data.objects.new("Iskelet", arm_data)
bpy.context.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for b in bones:
    eb = arm_data.edit_bones.new(b)
    h, t = mh.to_blender(J[b][0]), mh.to_blender(J[b][1])
    h[2] -= ground; t[2] -= ground
    eb.head, eb.tail = Vector(h), Vector(t)
    eb.roll = rig[b].get("roll", 0.0)
for b in bones:
    p = rig[b]["parent"]
    if p:
        arm_data.edit_bones[b].parent = arm_data.edit_bones[p]
        arm_data.edit_bones[b].use_connect = rig[b].get("use_connect", False)
bpy.ops.object.mode_set(mode="OBJECT")

for ob in objs:
    ob.parent = arm
    md = ob.modifiers.new("Armature", "ARMATURE"); md.object = arm
    md.use_deform_preserve_volume = True

# tel tel saç + sakal (iskelet modifier'ından sonra: animasyonla birlikte hareket eder)
face_pts = {g: BV[groups[g]].mean(0) for g in ("joint-l-eye", "joint-r-eye", "joint-mouth", "joint-head", "joint-jaw")}
hair_refs = np.array([r[0] for r in hair_clo["refs"]]).ravel()
groom.groom(body, BV, orig_index, groups, hair_refs, face_pts, head_w=Wb[:, bones.index("Head")])
for ob in (body,):
    sd = ob.modifiers.new("Subdivision", "SUBSURF"); sd.levels = 0; sd.render_levels = 1
for ob in objs[1:2]:  # kıyafet
    sd = ob.modifiers.new("Subdivision", "SUBSURF"); sd.levels = 0; sd.render_levels = 1

bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
print("KAYDEDILDI", OUT, "boy(m)=", round(float(BV[groups['body']][:, 2].max()), 3))
