"""Hızlı kontrol: bir klibi aktarır, birkaç kareyi düşük kalitede render eder.
python3 karakter/test_anim.py karakter.blend klip.bvh cikti_klasoru kare1,kare2,...
"""
import os, sys
import bpy
sys.path.insert(0, os.path.dirname(__file__))
import anim
from render_still import look_at

blend, bvh, out, frames = sys.argv[1], sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4].split(",")]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
arm = bpy.data.objects["Iskelet"]
act, n = anim.retarget(arm, bvh, os.path.basename(bvh)[:-4])
print("KARE", n)
body = bpy.data.objects["Govde"]
for md in body.modifiers:
    if md.type == "PARTICLE_SYSTEM":
        md.show_render = False
for o in sc.objects:
    if o.type == "LIGHT":
        pass
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.6, 0.65, 1)
bpy.ops.mesh.primitive_plane_add(size=40)
cd = bpy.data.cameras.new("c"); cd.lens = 35
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "CYCLES"; sc.cycles.samples = 8; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 640, 640
for f in frames:
    sc.frame_set(f)
    hips = arm.matrix_world @ arm.pose.bones["Hips"].head
    cam.location = (hips.x + 3.2, hips.y - 3.2, 1.3)
    look_at(cam, (hips.x, hips.y, 0.9))
    sc.render.filepath = os.path.join(out, f"f{f:04d}.png")
    bpy.ops.render.render(write_still=True)
print("TAMAM")
