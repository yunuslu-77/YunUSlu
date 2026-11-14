"""CMU BVH (cgspeed MotionBuilder isimleri) -> MPFB cmu_mb iskeletine hareket aktarımı.

Yöntem: BVH'de dinlenme pozunda tüm eklem eksenleri dünya ile hizalıdır; böylece her eklemin
dünya dönüşü D(j) = 'dinlenmeden bu yana dünya dönüşü' olur. Hedef kemik önce kaynağın dinlenme
yönüne hizalanır (C, sadece salınım), sonra D uygulanır:  P_hedef = D · C · R_hedef_dinlenme.
"""
import math
import numpy as np
import bpy
from mathutils import Matrix, Quaternion, Vector

LAST_ROOT_PATH = []
LAST_FACING = []
NAME_MAP = {"LeftHandIndex1": "LeftHandFinger1", "RightHandIndex1": "RightHandFinger1"}
CONV = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # BVH (Y-yukarı) -> Blender (Z-yukarı)


def parse_bvh(path):
    joints, stack, order = {}, [], []
    lines = open(path).read().split("\n")
    i = 0
    while i < len(lines):
        t = lines[i].strip().split()
        i += 1
        if not t:
            continue
        if t[0] in ("ROOT", "JOINT"):
            name = t[1]
            joints[name] = {"parent": stack[-1] if stack else None, "children": [], "channels": [], "end": None}
            if stack:
                joints[stack[-1]]["children"].append(name)
            order.append(name); stack.append(name)
        elif t[0] == "End":
            stack.append("__end__")
        elif t[0] == "OFFSET":
            off = np.array([float(x) for x in t[1:4]])
            if stack[-1] == "__end__":
                joints[stack[-2]]["end"] = off
            else:
                joints[stack[-1]]["offset"] = off
        elif t[0] == "CHANNELS":
            joints[stack[-1]]["channels"] = t[2:]
        elif t[0] == "}":
            stack.pop()
        elif t[0] == "MOTION":
            break
    nframes = int(lines[i].split()[1]); ftime = float(lines[i + 1].split()[2])
    data = np.array([[float(x) for x in l.split()] for l in lines[i + 2:i + 2 + nframes] if l.strip()])
    return joints, order, data, ftime


def _rot(axis, deg):
    a = math.radians(deg)
    return Matrix.Rotation(a, 3, axis)


def bvh_world(joints, order, data, step):
    """Her (alt-örneklenmiş) kare için: eklem dünya dönüşü (Blender ekseninde) ve konumu."""
    frames = []
    for row in data[::step]:
        c = 0
        W, P = {}, {}
        for j in order:
            J = joints[j]
            R = Matrix.Identity(3); pos = Vector(J["offset"])
            for ch in J["channels"]:
                v = row[c]; c += 1
                if ch.endswith("position"):
                    pos["XYZ".index(ch[0])] = v
                else:
                    R = R @ _rot(ch[0], v)
            if J["parent"] is None:
                W[j] = R; P[j] = pos
            else:
                p = J["parent"]
                W[j] = W[p] @ R
                P[j] = P[p] + W[p] @ Vector(J["offset"])
        frames.append({j: (CONV @ W[j] @ CONV.transposed(), CONV @ P[j]) for j in order})
    return frames


def retarget(arm, path, action_name, fps=30, ground_fix=True, max_seconds=None, start_seconds=0.0):
    joints, order, data, ftime = parse_bvh(path)
    step = max(1, round((1.0 / fps) / ftime))
    if max_seconds or start_seconds:
        a = int(start_seconds / ftime)
        b = a + int(max_seconds / ftime) if max_seconds else len(data)
        data = data[a:b]
    data = data[1:]  # cgspeed: ilk kare T-poz referansı
    frames = bvh_world(joints, order, data, step)

    bones = arm.data.bones
    rest_w = {b.name: b.matrix_local.copy() for b in bones}  # armature uzayı
    src_of = {}
    # ayak parmağı verisi CMU'da gürültülü: parmaklar ayağa sabit kalsın
    SKIP = {"LeftToeBase", "RightToeBase"}
    for j in order:
        t = NAME_MAP.get(j, j)
        if t in bones and t not in SKIP:
            src_of[t] = j

    # kaynak dinlenme yönleri (Blender ekseninde)
    def src_dir(j):
        J = joints[j]
        kids = J["children"]
        if J.get("end") is not None and not kids:
            v = J["end"]
        else:
            # hedef kemiğin kuyruğuna en uygun çocuk: hedef iskelette bu kemiğin çocuklarına bak
            t = NAME_MAP.get(j, j)
            tkids = [c.name for c in bones[t].children]
            cand = [k for k in kids if NAME_MAP.get(k, k) in tkids]
            if len(cand) > 1:
                tail = bones[t].tail_local
                cand.sort(key=lambda k: (bones[NAME_MAP.get(k, k)].head_local - tail).length)
            k = (cand or kids)[0]
            v = joints[k]["offset"]
        v = CONV @ Vector(v)
        return v.normalized() if v.length > 1e-6 else None

    # Yapısal kemikler (omurga, köprücük, kalça eklemi): kaynak ve hedef iskeletin dinlenme
    # geometrisi farklı olduğundan yön kopyalanmaz, yalnızca dinlenmeden farkı (D) aktarılır.
    STRUCT = {"Hips", "LowerBack", "Spine", "Spine1", "Neck", "Neck1", "Head",
              "LHipJoint", "RHipJoint", "LeftShoulder", "RightShoulder"}
    C = {}
    for t, j in src_of.items():
        if t in STRUCT:
            C[t] = Matrix.Identity(3)
            continue
        sd = src_dir(j)
        td = (bones[t].tail_local - bones[t].head_local).normalized()
        C[t] = td.rotation_difference(sd).to_matrix() if sd is not None else Matrix.Identity(3)

    # ölçek: bacak uzunluğu oranı
    def leg_len_src():
        return sum(np.linalg.norm(joints[k]["offset"]) for k in ("LeftLeg", "LeftFoot"))
    def leg_len_tgt():
        return bones["LeftUpLeg"].length + bones["LeftLeg"].length
    scale = leg_len_tgt() / leg_len_src()

    act = bpy.data.actions.new(action_name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act

    hips0 = frames[0]["Hips"][1]
    pbs = arm.pose.bones
    for pb in pbs:
        pb.rotation_mode = "QUATERNION"

    ordered = []  # hiyerarşi sırası
    def walk(b):
        ordered.append(b.name)
        for c in b.children:
            walk(c)
    for b in bones:
        if b.parent is None:
            walk(b)

    head_rest = {n: rest_w[n].to_translation() for n in rest_w}
    FEET = {"LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"}

    # 1. geçiş: her kare için kemik dünya dönüşleri, kök konumu ve ayak yükseklikleri
    poses, roots, lows = [], [], []
    for f in frames:
        pose_w, pos = {}, {}
        for name in ordered:
            Rt = rest_w[name].to_3x3()
            par = bones[name].parent
            if name in src_of:
                Pw = f[src_of[name]][0] @ C[name] @ Rt
            else:  # kaynakta yoksa ebeveyninin hareketini izle
                Pw = (pose_w[par.name] @ rest_w[par.name].to_3x3().inverted() @ Rt) if par else Rt
            pose_w[name] = Pw
            if par is None:
                loc = f["Hips"][1]
                pos[name] = Vector(((loc.x - hips0.x) * scale, (loc.y - hips0.y) * scale, loc.z * scale))
            else:
                off = rest_w[par.name].to_3x3().inverted() @ (head_rest[name] - head_rest[par.name])
                pos[name] = pos[par.name] + pose_w[par.name] @ off
        poses.append(pose_w); roots.append(pos[ordered[0]])
        lows.append(min(pos[k].z - head_rest[k].z for k in FEET))
    # zemin: temas karelerinde ayak eklemleri dinlenme yüksekliğine otursun
    dz = -float(np.percentile(lows, 4)) if ground_fix else 0.0

    # 2. geçiş: yerel (basis) dönüşler ve anahtar kareler
    prev_q = {}
    for fi, pose_w in enumerate(poses):
        for name in ordered:
            b = bones[name]
            Pw = pose_w[name]
            if b.parent is None:
                P = roots[fi] + Vector((0, 0, dz))
                basis = rest_w[name].inverted() @ (Matrix.Translation(P) @ Pw.to_4x4())
            else:
                par = b.parent
                rr = (rest_w[par.name].inverted() @ rest_w[name]).to_3x3().to_4x4()
                basis = rr.inverted() @ pose_w[par.name].to_4x4().inverted() @ Pw.to_4x4()
            q = basis.to_quaternion()
            if name in prev_q and prev_q[name].dot(q) < 0:
                q.negate()
            prev_q[name] = q
            pb = pbs[name]
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=fi + 1, group=name)
            if b.parent is None:
                pb.location = basis.to_translation()
                pb.keyframe_insert("location", frame=fi + 1, group=name)
    act.frame_range = (1, len(frames))
    global LAST_ROOT_PATH, LAST_FACING  # kalça yolu ve bakış yönü — kamera takibi için
    LAST_ROOT_PATH = [r + Vector((0, 0, dz)) for r in roots]
    LAST_FACING = []
    for pw in poses:
        fwd = pw["Hips"] @ rest_w["Hips"].to_3x3().inverted() @ Vector((0, -1, 0))
        fwd.z = 0
        LAST_FACING.append(fwd.normalized() if fwd.length > 1e-6 else Vector((0, -1, 0)))
    return act, len(frames)
