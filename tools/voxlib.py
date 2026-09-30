"""Voxel character toolkit: voxel painting, skinned meshing, palette texture and GLB export.

Coordinate system: Y up, character faces +Z, character's left is +X.
Voxel (i, j, k) spans [i, i+1] x [j, j+1] x [k, k+1] voxel units (S metres each).
"""
import io
import json
import math
import struct

import numpy as np
from PIL import Image

S = 0.026  # voxel size in metres (same as heroine.glb)


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mir(i):
    """Mirror a voxel x index across the centre plane."""
    return -1 - i


def xr(side, a, b):
    """x range [a, b) on the left (+X) side, mirrored for the right side."""
    return (a, b) if side == 'L' else (-b, -a)


class Vox:
    def __init__(self):
        self.v = {}

    def put(self, i, j, k, c, b, jit=1.0):
        self.v[(i, j, k)] = (c, b, jit)

    def box(self, x0, x1, y0, y1, z0, z1, c, b, jit=1.0, only_empty=False):
        for i in range(x0, x1):
            for j in range(y0, y1):
                for k in range(z0, z1):
                    if only_empty and (i, j, k) in self.v:
                        continue
                    self.v[(i, j, k)] = (c, b, jit)

    def paint(self, i, j, k, c, jit=None):
        if (i, j, k) in self.v:
            oc, b, oj = self.v[(i, j, k)]
            self.v[(i, j, k)] = (c, b, oj if jit is None else jit)

    def pbox(self, x0, x1, y0, y1, z0, z1, c, jit=None):
        for i in range(x0, x1):
            for j in range(y0, y1):
                for k in range(z0, z1):
                    self.paint(i, j, k, c, jit)

    def rm(self, i, j, k):
        self.v.pop((i, j, k), None)

    def get(self, i, j, k):
        return self.v.get((i, j, k))


# ---------------------------------------------------------------- meshing
FACES = [
    ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
]


def _hash(i, j, k):
    h = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return (h ^ (h >> 16)) & 0xffff


def resolve_color(pal, name):
    seen = 0
    while isinstance(pal.get(name), str) and not pal[name].startswith('#'):
        name = pal[name]
        seen += 1
        if seen > 10:
            raise ValueError(name)
    return hexc(pal[name])


def build_mesh(vox, pal, joint_index):
    colors = {}
    pos, nrm, cid, jnt = [], [], [], []
    for (i, j, k), (c, b, jit) in vox.v.items():
        rgb = resolve_color(pal, c)
        if jit:
            lv = (_hash(i, j, k) % 5) - 2  # -2..2
            f = 1.0 + 0.012 * lv * jit
            rgb = tuple(max(0, min(255, int(round(x * f)))) for x in rgb)
        ci = colors.setdefault(rgb, len(colors))
        bi = joint_index[b]
        for (dx, dy, dz), corners in FACES:
            nb = vox.v.get((i + dx, j + dy, k + dz))
            if nb is not None and nb[1] == b:
                continue
            for (cx, cy, cz) in corners:
                pos.append(((i + cx) * S, (j + cy) * S, (k + cz) * S))
                nrm.append((dx, dy, dz))
                cid.append(ci)
                jnt.append(bi)
    nq = len(pos) // 4
    idx = []
    for q in range(nq):
        o = q * 4
        idx += [o, o + 1, o + 2, o, o + 2, o + 3]
    # palette texture: 4x4 px cells, 64 cells per row
    cell, per_row = 4, 64
    rows = (len(colors) + per_row - 1) // per_row
    hgt = 4
    while hgt < rows * cell:
        hgt *= 2
    img = Image.new('RGB', (per_row * cell, hgt), (255, 0, 255))
    px = img.load()
    for rgb, n in colors.items():
        cx, cy = (n % per_row) * cell, (n // per_row) * cell
        for a in range(cell):
            for bb in range(cell):
                px[cx + a, cy + bb] = rgb
    W, Hh = img.size
    uv = []
    for n in cid:
        cx, cy = (n % per_row) * cell + cell / 2, (n // per_row) * cell + cell / 2
        uv.append((cx / W, cy / Hh))
    return dict(pos=np.array(pos, np.float32), nrm=np.array(nrm, np.float32),
                uv=np.array(uv, np.float32), jnt=np.array(jnt, np.uint8),
                idx=np.array(idx, np.uint32), img=img, ncolors=len(colors))


# ---------------------------------------------------------------- math
def quat_euler(rx, ry, rz):
    """q = qy * qx * qz (Z applied first, then X, then Y)."""
    def qa(ax, a):
        s = math.sin(a / 2)
        return np.array([ax[0] * s, ax[1] * s, ax[2] * s, math.cos(a / 2)])

    def mul(a, b):
        x1, y1, z1, w1 = a
        x2, y2, z2, w2 = b
        return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                         w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                         w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
                         w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])
    return mul(mul(qa((0, 1, 0), ry), qa((1, 0, 0), rx)), qa((0, 0, 1), rz))


# ---------------------------------------------------------------- GLB export
def write_glb(path, name, vox, pal, bones, clips, fps=30):
    """bones: list of (name, parent or None, pivot voxel coords (x,y,z)).
    clips: list of (clip_name, duration, pose_fn) where pose_fn(t) -> (rot dict, hips offset metres)."""
    bnames = [b[0] for b in bones]
    joint_index = {n: i for i, n in enumerate(bnames)}
    mesh = build_mesh(vox, pal, joint_index)

    blob = bytearray()
    views, accs = [], []

    def add_view(data, target=None):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        blob.extend(data)
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
        if target:
            v['target'] = target
        views.append(v)
        return len(views) - 1

    def add_acc(arr, ctype, typ, target=None, minmax=False, normalized=False):
        arr = np.ascontiguousarray(arr)
        bv = add_view(arr.tobytes(), target)
        a = {'bufferView': bv, 'componentType': ctype, 'count': int(arr.shape[0]), 'type': typ}
        if normalized:
            a['normalized'] = True
        if minmax:
            flat = arr.reshape(arr.shape[0], -1)
            a['min'] = [float(x) for x in flat.min(0)]
            a['max'] = [float(x) for x in flat.max(0)]
        accs.append(a)
        return len(accs) - 1

    n = len(mesh['pos'])
    a_pos = add_acc(mesh['pos'], 5126, 'VEC3', 34962, minmax=True)
    a_nrm = add_acc(mesh['nrm'], 5126, 'VEC3', 34962)
    a_uv = add_acc(mesh['uv'], 5126, 'VEC2', 34962)
    j4 = np.zeros((n, 4), np.uint8)
    j4[:, 0] = mesh['jnt']
    a_j = add_acc(j4, 5121, 'VEC4', 34962)
    w4 = np.zeros((n, 4), np.float32)
    w4[:, 0] = 1.0
    a_w = add_acc(w4, 5126, 'VEC4', 34962)
    idx = mesh['idx']
    if n < 65536:
        a_i = add_acc(idx.astype(np.uint16), 5123, 'SCALAR', 34963)
    else:
        a_i = add_acc(idx, 5125, 'SCALAR', 34963)

    # skeleton
    piv = {b[0]: np.array(b[2], float) for b in bones}
    parent = {b[0]: b[1] for b in bones}
    ibm = []
    for bn in bnames:
        m = np.eye(4, dtype=np.float32)
        m[:3, 3] = -piv[bn] * S
        ibm.append(m.T.reshape(16))  # column-major
    a_ibm = add_acc(np.array(ibm, np.float32), 5126, 'MAT4')

    png = io.BytesIO()
    mesh['img'].save(png, 'PNG')
    bv_img = add_view(png.getvalue())

    # nodes: 0.. joints, then mesh node, then character root node
    nodes = []
    for bn in bnames:
        p = parent[bn]
        t = piv[bn] - (piv[p] if p else 0)
        nd = {'name': bn, 'translation': [float(x) * S for x in t]}
        ch = [joint_index[c] for c in bnames if parent[c] == bn]
        if ch:
            nd['children'] = ch
        nodes.append(nd)
    mesh_node = len(nodes)
    nodes.append({'name': name + '_Skin', 'mesh': 0, 'skin': 0})
    root_node = len(nodes)
    nodes.append({'name': name, 'children': [mesh_node, joint_index['Root']]})

    # animations
    anims = []
    for cname, dur, fn in clips:
        nk = int(round(dur * fps)) + 1
        times = np.linspace(0, dur, nk).astype(np.float32)
        rots = {bn: [] for bn in bnames}
        hips_t = []
        for t in times:
            rot, off = fn(float(t))
            for bn in bnames:
                rots[bn].append(quat_euler(*rot.get(bn, (0, 0, 0))))
            hips_t.append(piv['Hips'] - piv['Root'] + np.array(off) / S)
        a_t = add_acc(times.reshape(-1, 1), 5126, 'SCALAR', minmax=True)
        samplers, chans = [], []
        for bn in bnames:
            q = np.array(rots[bn], np.float32)
            # keep quaternion hemisphere continuous
            for r in range(1, len(q)):
                if np.dot(q[r], q[r - 1]) < 0:
                    q[r] = -q[r]
            a_o = add_acc(q, 5126, 'VEC4')
            samplers.append({'input': a_t, 'output': a_o, 'interpolation': 'LINEAR'})
            chans.append({'sampler': len(samplers) - 1, 'target': {'node': joint_index[bn], 'path': 'rotation'}})
        ht = (np.array(hips_t) * S).astype(np.float32)
        a_o = add_acc(ht, 5126, 'VEC3')
        samplers.append({'input': a_t, 'output': a_o, 'interpolation': 'LINEAR'})
        chans.append({'sampler': len(samplers) - 1, 'target': {'node': joint_index['Hips'], 'path': 'translation'}})
        anims.append({'name': cname, 'samplers': samplers, 'channels': chans})

    gltf = {
        'asset': {'version': '2.0', 'generator': 'GLBmodel voxlib'},
        'scene': 0,
        'scenes': [{'name': 'Scene', 'nodes': [root_node]}],
        'nodes': nodes,
        'meshes': [{'name': name + '_Skin', 'primitives': [{
            'attributes': {'POSITION': a_pos, 'NORMAL': a_nrm, 'TEXCOORD_0': a_uv,
                           'JOINTS_0': a_j, 'WEIGHTS_0': a_w},
            'indices': a_i, 'material': 0}]}],
        'skins': [{'name': name + '_Rig', 'inverseBindMatrices': a_ibm,
                   'joints': list(range(len(bnames))), 'skeleton': joint_index['Root']}],
        'materials': [{'name': name, 'pbrMetallicRoughness': {
            'baseColorTexture': {'index': 0}, 'metallicFactor': 0.0, 'roughnessFactor': 0.8}}],
        'textures': [{'sampler': 0, 'source': 0}],
        'images': [{'name': name + '_Palette', 'mimeType': 'image/png', 'bufferView': bv_img}],
        'samplers': [{'magFilter': 9728, 'minFilter': 9728, 'wrapS': 33071, 'wrapT': 33071}],
        'animations': anims,
        'accessors': accs,
        'bufferViews': views,
        'buffers': [{'byteLength': 0}],
    }
    while len(blob) % 4:
        blob.append(0)
    gltf['buffers'][0]['byteLength'] = len(blob)
    js = json.dumps(gltf, separators=(',', ':')).encode()
    while len(js) % 4:
        js += b' '
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<II', len(js), 0x4E4F534A))
        f.write(js)
        f.write(struct.pack('<II', len(blob), 0x004E4942))
        f.write(blob)
    return dict(verts=n, tris=len(idx) // 3, voxels=len(vox.v), colors=mesh['ncolors'])
