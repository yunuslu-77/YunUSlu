"""Stüdyo ışığında portre / tam boy test render'ları.
python3 karakter/render_still.py karakter.blend cikti_klasoru [samples]
"""
import math, os, sys
import bpy
from mathutils import Vector


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_studio(sc):
    w = bpy.data.worlds.new("Dunya"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.045, 0.05, 0.06, 1); bg.inputs["Strength"].default_value = 1.0
    lights = [  # (isim, konum, güç W, boyut, renk)
        ("Ana", (1.6, -2.2, 2.4), 450, 1.2, (1.0, 0.93, 0.85)),
        ("Dolgu", (-2.2, -1.6, 1.6), 120, 2.0, (0.8, 0.88, 1.0)),
        ("Kontur", (-0.8, 2.4, 2.6), 500, 0.8, (0.85, 0.92, 1.0)),
        ("Kontur2", (1.4, 2.0, 1.9), 300, 0.6, (1.0, 0.85, 0.7)),
    ]
    for n, loc, p, size, col in lights:
        ld = bpy.data.lights.new(n, "AREA"); ld.energy = p; ld.size = size; ld.color = col
        lo = bpy.data.objects.new(n, ld); sc.collection.objects.link(lo); lo.location = loc
        look_at(lo, (0, 0, 1.3))
    # zemin
    bpy.ops.mesh.primitive_plane_add(size=30)
    fl = bpy.context.object; fl.name = "Zemin"
    m = bpy.data.materials.new("Zemin"); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.05, 0.05, 0.055, 1); b.inputs["Roughness"].default_value = 0.35
    fl.data.materials.append(m)


def render_settings(sc, res=(1080, 1350), samples=64):
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
    sc.cycles.samples = samples; sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Punchy"


def cam(sc, name, loc, target, lens):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.8 if lens > 60 else 5.6
    co = bpy.data.objects.new(name, cd); sc.collection.objects.link(co)
    co.location = loc; look_at(co, target)
    cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
    return co


if __name__ == "__main__":
    blend, outdir = sys.argv[1], sys.argv[2]
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    setup_studio(sc); render_settings(sc, samples=samples)
    head_z = max((v.co.z for v in bpy.data.objects["Govde"].data.vertices))
    shots = {
        "portre": cam(sc, "Portre", (0.55, -1.25, head_z - 0.05), (0, 0, head_z - 0.12), 85),
        "tamboy": cam(sc, "Tamboy", (1.6, -4.6, 1.05), (0, 0, head_z * 0.52), 50),
        "profil": cam(sc, "Profil", (1.35, -0.25, head_z - 0.08), (0, 0, head_z - 0.12), 85),
    }
    only = os.environ.get("SHOTS")
    for n, c in shots.items():
        if only and n not in only.split(","):
            continue
        sc.camera = c; sc.render.filepath = os.path.join(outdir, n + ".png")
        bpy.ops.render.render(write_still=True)
        print("RENDER", n)
