"""Seçilen klipleri takip kamerasıyla PNG kareleri olarak render eder.
python3 karakter/render_anim.py karakter.blend bvh_klasoru cikti_klasoru klip1,klip2 [samples] [genislik]
Her klip için cikti/<klip>/#### .png yazar (var olan kareleri atlar: kaldığı yerden devam eder).
"""
import math, os, sys
import numpy as np
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import anim
from clips import CLIPS
from render_still import look_at, setup_studio, render_settings

blend, bdir, out, names = sys.argv[1:5]
samples = int(sys.argv[5]) if len(sys.argv) > 5 else 24
width = int(sys.argv[6]) if len(sys.argv) > 6 else 1280
names = names.split(",")
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
arm = bpy.data.objects["Iskelet"]
setup_studio(sc)
render_settings(sc, res=(width, width * 9 // 16), samples=samples)
sc.render.fps = 30
sc.render.use_persistent_data = True
sc.render.use_simplify = True
sc.render.simplify_child_particles_render = float(os.environ.get("CHILD", "0.5"))
cy = sc.cycles
cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 6, 2, 2
cy.transmission_bounces, cy.transparent_max_bounces = 4, 8
cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.03

# ışıkları karakterle birlikte taşı (sahne geniş hareketlerde de aydınlık kalsın)
rig = bpy.data.objects.new("IsikRig", None); sc.collection.objects.link(rig)
for o in list(sc.objects):
    if o.type == "LIGHT":
        o.parent = rig
cd = bpy.data.cameras.new("Kamera"); cd.lens = 40
cd.dof.use_dof = True; cd.dof.aperture_fstop = 4.0
cam = bpy.data.objects.new("Kamera", cd); sc.collection.objects.link(cam); sc.camera = cam

lookup = {c[0]: c for c in CLIPS}
for name in names:
    _, clip, st, du, cat = lookup[name]
    act, n = anim.retarget(arm, os.path.join(bdir, clip + ".bvh"), name, start_seconds=st, max_seconds=du)
    sc.frame_start, sc.frame_end = 1, n
    # kalça yolunu yumuşat (kamera titremesin)
    H = np.array([[v.x, v.y, v.z] for v in anim.LAST_ROOT_PATH])
    k = 25
    pad = np.pad(H, ((k, k), (0, 0)), mode="edge")
    ker = np.hanning(2 * k + 1); ker /= ker.sum()
    Hs = np.stack([np.convolve(pad[:, i], ker, mode="valid") for i in range(3)], 1)
    span = np.ptp(H[:, :2], axis=0).max()
    dist = 5.2 + min(span, 6.0) * 0.25
    ang = math.radians(-35)
    off = Vector((math.sin(ang) * dist, -math.cos(ang) * dist, 0))
    for f in range(1, n + 1):
        c = Vector(Hs[f - 1])
        cam.location = Vector((c.x, c.y, 1.25)) + off
        look_at(cam, (c.x, c.y, 0.95))
        cd.dof.focus_distance = (cam.location - Vector((c.x, c.y, 0.95))).length
        cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
        cd.keyframe_insert("dof.focus_distance", frame=f)
        rig.location = (c.x, c.y, 0); rig.keyframe_insert("location", frame=f)
    od = os.path.join(out, name); os.makedirs(od, exist_ok=True)
    for f in range(1, n + 1):
        p = os.path.join(od, f"{f:04d}.png")
        if os.path.exists(p):
            continue
        sc.frame_set(f)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
    print("KLIP_BITTI", name, n, flush=True)
