"""Tel tel saç ve sakal (Blender parçacık saçı + Principled Hair BSDF)."""
import numpy as np
import bpy


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def set_group(ob, name, weights, orig_index):
    """weights: tam (orijinal) vertex dizini üzerinde; orig_index: mesh vertex -> orijinal indeks."""
    vg = ob.vertex_groups.new(name=name)
    for i, oi in enumerate(orig_index):
        w = float(weights[oi])
        if w > 0.002:
            vg.add([i], w, "REPLACE")
    return vg


def hair_material(name, melanin=0.88, redness=0.35, rough=0.32, radial=0.3, coat=0.0,
                  dark=(0.012, 0.009, 0.007, 1), dark_mix=0.75):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    h = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    h.parametrization = "MELANIN"
    h.inputs["Melanin"].default_value = melanin
    h.inputs["Melanin Redness"].default_value = redness
    h.inputs["Roughness"].default_value = rough
    h.inputs["Radial Roughness"].default_value = radial
    h.inputs["Coat"].default_value = coat
    # tel bazında hafif renk ve parlaklık farkı
    info = nt.nodes.new("ShaderNodeHairInfo")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = melanin - 0.06
    mr.inputs["To Max"].default_value = min(1.0, melanin + 0.06)
    nt.links.new(info.outputs["Random"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], h.inputs["Melanin"])
    # ince teller güçlü alan ışıklarında gri parlıyor: koyu dağınık bileşenle dengele
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs["Color"].default_value = dark
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs["Fac"].default_value = dark_mix
    nt.links.new(h.outputs["BSDF"], mx.inputs[1]); nt.links.new(d.outputs["BSDF"], mx.inputs[2])
    nt.links.new(mx.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    return m


def add_hair(ob, name, density_vg, length_vg, mat_name, count, children, length,
             root=0.00006, tip=0.00002, align=(0, 0, 0), normal=1.0,
             clump=0.0, rough1=0.0, rough_end=0.0, rough2=0.0, kink=None, random=0.15):
    md = ob.modifiers.new(name, "PARTICLE_SYSTEM")
    ps = ob.particle_systems[md.name]
    st = ps.settings
    st.name = name
    st.type = "HAIR"
    st.use_advanced_hair = True
    st.count = count
    st.hair_length = length
    st.hair_step = 5
    st.display_step = 3
    st.render_step = 4
    # gelişmiş modda tel uzunluğu = başlangıç hızı; yön: normal + nesne ekseni (uzunluk oranı olarak)
    st.normal_factor = length * normal
    st.object_align_factor = tuple(a * length for a in align)
    st.factor_random = random * length
    st.emit_from = "FACE"
    st.use_emit_random = True
    st.distribution = "JIT"
    st.child_type = "INTERPOLATED"
    st.child_percent = 1
    st.rendered_child_count = children
    st.child_length = 1.0
    st.child_length_threshold = 0.1
    st.clump_factor = clump
    st.clump_shape = 0.2
    st.roughness_1 = rough1
    st.roughness_1_size = 1.0
    st.roughness_endpoint = rough_end
    st.roughness_end_shape = 1.0
    st.roughness_2 = rough2
    st.roughness_2_size = 1.0
    st.child_radius = 0.004
    st.child_roundness = 0.5
    if kink:
        st.kink = "WAVE"; st.kink_amplitude, st.kink_frequency = kink
    st.root_radius = 1.0
    st.radius_scale = root
    st.tip_radius = tip / root
    st.use_close_tip = True
    st.material_slot = mat_name
    ps.vertex_group_density = density_vg
    if length_vg:
        ps.vertex_group_length = length_vg
    ps.seed = abs(hash(name)) % 1000
    return ps


def measured_length(ob, name, n=3000):
    dg = bpy.context.evaluated_depsgraph_get()
    ps = ob.evaluated_get(dg).particle_systems[name]
    L = []
    for p in list(ps.particles)[:n]:
        k = p.hair_keys
        if len(k) > 1:
            L.append(sum((k[i + 1].co - k[i].co).length for i in range(len(k) - 1)))
    return float(np.median(L)) if L else 0.0


def calibrate(ob, name, target, iters=3):
    """Tel uzunluğunu ölçüp hız parametrelerini hedef medyan uzunluğa ölçekler."""
    st = ob.particle_systems[name].settings
    for _ in range(iters):
        m = measured_length(ob, name)
        if m <= 0:
            break
        k = target / m
        if abs(k - 1) < 0.03:
            break
        st.normal_factor *= k
        st.object_align_factor = tuple(a * k for a in st.object_align_factor)
        st.factor_random *= k
    return measured_length(ob, name)


def groom(body, V_bl, orig_index, groups, hair_refs, face_pts, head_w):
    """V_bl: orijinal indeksli Blender koordinatları; hair_refs: saç proxy'sinin referans vertexleri."""
    E = (face_pts["joint-l-eye"] + face_pts["joint-r-eye"]) / 2
    M = face_pts["joint-mouth"]
    H = face_pts["joint-head"]
    x, y, z = V_bl[:, 0], V_bl[:, 1], V_bl[:, 2]
    n = len(V_bl)
    in_body = np.zeros(n, bool); in_body[groups["body"]] = True

    # --- kafa derisi: geometriden (kafa kemiğine bağlı, yüz/kulak hariç)
    ax = np.abs(x - H[0])
    skull = in_body * smoothstep(0.25, 0.55, head_w)
    # kulak: kafanın kulak hizasındaki en dış noktası çevresi
    lvl = (skull > 0.5) & (np.abs(z - (E[2] - 0.015)) < 0.015)
    ear_x = np.percentile(ax[lvl], 99) if lvl.any() else 0.08
    ear_c = V_bl[lvl & (ax > ear_x - 0.01)].mean(0) if lvl.any() else H
    ear = (ax > ear_x - 0.011) & (np.abs(y - ear_c[1]) < 0.035) & (z < E[2] + 0.008) & (z > E[2] - 0.06)
    front = smoothstep(E[1] + 0.045, E[1] + 0.02, y)          # 1 = alın/yüz düzlemi
    hl = E[2] + 0.062 - smoothstep(0.02, 0.06, ax) * 0.02      # şakaklarda saç çizgisi hafif geride
    face_cut = front * smoothstep(hl + 0.006, hl - 0.006, z)
    # ense ve arka kafa (boyun kemiğine bağlı olsa da) dahil; alt sınır önden arkaya alçalır
    back = smoothstep(ear_c[1] - 0.01, ear_c[1] + 0.03, y)
    lower = (E[2] - 0.035) * (1 - back) + (M[2] - 0.01) * back
    nape = in_body * (z > M[2] - 0.03) * (ax < 0.07) * back
    scalp = np.maximum(skull, nape) * ~ear * (1 - face_cut) * smoothstep(lower - 0.008, lower + 0.008, z)
    scalp = np.clip(scalp, 0, 1)
    # üst bölge (uzun saç) ve kısa yanlar (fade)
    top = scalp * smoothstep(E[2] + 0.045, E[2] + 0.075, z) * (1 - smoothstep(0.048, 0.064, ax))
    top_len = 0.75 + 0.25 * smoothstep(H[1] + 0.02, H[1] - 0.06, y)   # önde biraz daha uzun
    fade_len = 0.35 + 0.65 * smoothstep(E[2] - 0.02, E[2] + 0.06, z)  # aşağıdan yukarı uzar

    # --- sakal (kısa, sık, kirli sakal)
    front = y < H[1] - 0.005
    ztop = E[2] - 0.05 + np.clip(ax - 0.045, 0, None) * 1.4  # yanakta alçak, favoriye yükselir
    beard = smoothstep(ztop + 0.006, ztop - 0.008, z)            # üst sınır (yumuşak)
    beard *= smoothstep(M[2] - 0.085, M[2] - 0.06, z)            # çene altında biter
    beard *= front * in_body * (ax < 0.078)
    beard *= 1 - smoothstep(0.068, 0.078, ax)
    # dudakları hariç tut (elips)
    lip = ((x - M[0]) / 0.027) ** 2 + ((z - M[2]) / 0.011) ** 2
    beard *= smoothstep(0.9, 1.35, lip)
    # boyunda seyrelt
    beard *= 0.5 + 0.5 * smoothstep(M[2] - 0.07, M[2] - 0.045, z)

    set_group(body, "sac_ust", top, orig_index)
    set_group(body, "sac_ust_uzunluk", top_len * (top > 0), orig_index)
    set_group(body, "sac_yan", scalp, orig_index)
    set_group(body, "sac_yan_uzunluk", fade_len * (scalp > 0), orig_index)
    set_group(body, "sakal", beard, orig_index)
    # deri shader'ı için maske öznitelikleri (kıl kökü gölgesi)
    for nm, arr in (("sac_maske", scalp), ("sakal_maske", beard)):
        at = body.data.attributes.new(nm, "FLOAT", "POINT")
        at.data.foreach_set("value", arr[orig_index].astype(np.float32))

    body.data.materials.append(hair_material("SacTeli", melanin=0.985, redness=0.08, rough=0.38, radial=0.5))
    body.data.materials.append(hair_material("SakalTeli", melanin=0.985, redness=0.06, rough=0.5, dark_mix=0.9))

    add_hair(body, "Sac", "sac_ust", "sac_ust_uzunluk", "SacTeli",
             count=9000, children=18, length=0.05, root=0.0001, tip=0.00002,
             normal=0.35, align=(0.0, 0.85, 0.35), clump=0.4, rough1=0.003,
             rough_end=0.005, rough2=0.0012, random=0.2)
    body.data.materials.append(hair_material("SacYanTeli", melanin=0.985, redness=0.06, rough=0.5, dark_mix=0.9))
    add_hair(body, "SacYan", "sac_yan", "sac_yan_uzunluk", "SacYanTeli",
             count=22000, children=6, length=0.006, root=0.00007, tip=0.00002,
             normal=0.5, align=(0.0, 0.6, -0.5), rough1=0.0004, rough_end=0.0006, random=0.3)
    add_hair(body, "Sakal", "sakal", None, "SakalTeli",
             count=26000, children=6, length=0.0032, root=0.00008, tip=0.00002,
             normal=0.8, align=(0, 0, -0.6), rough1=0.0003, rough_end=0.0005, random=0.5)
    print("sac uzunluk (m):", round(calibrate(body, "Sac", 0.04), 4))
    print("yan uzunluk (m):", round(calibrate(body, "SacYan", 0.005), 4))
    print("sakal uzunluk (m):", round(calibrate(body, "Sakal", 0.0025), 4))
    return scalp, beard
