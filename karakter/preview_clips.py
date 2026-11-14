"""Her klipten eşit aralıklı 6 kare: düşük kaliteli önizleme kontak sayfası.
python3 karakter/preview_clips.py karakter.blend bvh_klasoru cikti_klasoru [klip,klip...]
"""
import os, sys
import bpy
sys.path.insert(0, os.path.dirname(__file__))
import anim
from clips import CLIPS
from render_still import look_at

blend, bdir, out = sys.argv[1:4]
only = sys.argv[4].split(",") if len(sys.argv) > 4 else None
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
arm = bpy.data.objects["Iskelet"]
for md in bpy.data.objects["Govde"].modifiers:
    if md.type in ("PARTICLE_SYSTEM", "SUBSURF"):
        md.show_render = False
for o in sc.objects:
    if o.type == "MESH" and "Subdivision" in o.modifiers:
        o.modifiers["Subdivision"].show_render = False
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.6, 0.65, 1)
bpy.ops.mesh.primitive_plane_add(size=60)
cd = bpy.data.cameras.new("c"); cd.lens = 28
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "CYCLES"; sc.cycles.samples = 4; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 320, 320
for name, clip, st, du, cat in CLIPS:
    if only and name not in only:
        continue
    act, n = anim.retarget(arm, os.path.join(bdir, clip + ".bvh"), name, start_seconds=st, max_seconds=du)
    for k in range(6):
        f = 1 + int(k * (n - 1) / 5)
        sc.frame_set(f)
        hips = arm.matrix_world @ arm.pose.bones["Hips"].head
        cam.location = (hips.x + 3.5, hips.y - 3.5, 1.4)
        look_at(cam, (hips.x, hips.y, 0.8))
        sc.render.filepath = os.path.join(out, f"{name}_{k}.png")
        bpy.ops.render.render(write_still=True)
    print("KLIP", name, n, "kare")
