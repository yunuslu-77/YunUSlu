"""Tüm animasyonları ekler; .blend (tam kalite), FBX ve GLB (oyun motoru) dışa aktarır.
python3 karakter/export.py karakter.blend bvh_klasoru cikti_klasoru
"""
import os, sys
import bpy
sys.path.insert(0, os.path.dirname(__file__))
import anim
from clips import CLIPS

blend, bdir, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
sc.render.fps = 30
arm = bpy.data.objects["Iskelet"]

# 1) animasyonlar
for name, clip, st, du, cat in CLIPS:
    act, n = anim.retarget(arm, os.path.join(bdir, clip + ".bvh"), name, start_seconds=st, max_seconds=du)
    print("ANIM", name, n)
arm.animation_data.action = bpy.data.actions["bekleme_2"]
sc.frame_start, sc.frame_end = 1, int(bpy.data.actions["bekleme_2"].frame_range[1])
# her aksiyonu NLA izine koy (Blender içinde kolay seçim)
for act in [a for a in bpy.data.actions if a.name in {c[0] for c in CLIPS}]:
    tr = arm.animation_data.nla_tracks.new(); tr.name = act.name; tr.mute = True
    tr.strips.new(act.name, 1, act)
bpy.ops.file.pack_all()  # dokuları .blend içine göm (başka bilgisayarda da açılsın)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "karakter.blend"))
print("BLEND_KAYDEDILDI")

# 2) oyun sürümü: deri rengini (bronz ton + tıraş gölgesi dahil) dokuya pişir
body = bpy.data.objects["Govde"]
for md in list(body.modifiers):
    if md.type in ("PARTICLE_SYSTEM",):
        body.modifiers.remove(md)
img = bpy.data.images.new("Deri_Bake", 2048, 2048)
skin = body.data.materials["Deri"]
nt = skin.node_tree
tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = img
nt.nodes.active = tn
sc.render.engine = "CYCLES"; sc.cycles.samples = 16; sc.cycles.device = "CPU"
for o in sc.objects:
    o.select_set(False)
body.select_set(True); bpy.context.view_layer.objects.active = body
# bake sırasında iskelet pozu dinlenmede olsun
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0)
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8, use_clear=True)
img.filepath_raw = os.path.join(out, "deri_renk.png"); img.file_format = "PNG"; img.save()
print("BAKE_TAMAM")
# oyun materyali: pişmiş renk + aynı pürüzlülük
gm = bpy.data.materials.new("Deri_Oyun"); gm.use_nodes = True
b = gm.node_tree.nodes["Principled BSDF"]
t = gm.node_tree.nodes.new("ShaderNodeTexImage"); t.image = img
gm.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.5
b.inputs["Subsurface Weight"].default_value = 0.2
body.data.materials[0] = gm
# saç/sakal materyal yuvalarını kaldır (teller oyun dosyasında yok)
while len(body.data.materials) > 1:
    body.data.materials.pop()
# göz: cam kornea yerine düz doku (glTF/FBX uyumlu)
eye = bpy.data.objects["Gozler"]
em = bpy.data.materials.new("Goz_Oyun"); em.use_nodes = True
eb = em.node_tree.nodes["Principled BSDF"]
et = em.node_tree.nodes.new("ShaderNodeTexImage")
et.image = [n.image for n in eye.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE"][0]
em.node_tree.links.new(et.outputs["Color"], eb.inputs["Base Color"])
em.node_tree.links.new(et.outputs["Alpha"], eb.inputs["Alpha"])
eb.inputs["Roughness"].default_value = 0.1
eye.data.materials[0] = em
bpy.data.objects["Sac_Kart"].hide_render = False

for o in sc.objects:
    o.select_set(o.type in ("MESH", "ARMATURE") and o.name != "Zemin")
bpy.ops.export_scene.fbx(filepath=os.path.join(out, "karakter.fbx"), use_selection=True,
                         add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=True,
                         bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.5,
                         path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE")
print("FBX_TAMAM")
bpy.ops.export_scene.gltf(filepath=os.path.join(out, "karakter.glb"), export_format="GLB",
                          use_selection=True, export_animations=True, export_animation_mode="ACTIONS",
                          export_apply=False, export_image_format="JPEG", export_jpeg_quality=90)
print("GLB_TAMAM")
