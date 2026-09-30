"""Voxel character engine v2.

Compared with voxlib.py this adds
  * soft skinning around joints (2 influences, position based, watertight),
  * a "Blink" morph target (eyelid quads that slide over the eyes),
  * forward kinematics so every animation frame can be snapped to the ground,
  * a single palette texture shared by the body and the eyelids.

Coordinate system: Y up, the character faces +Z, the character's left is +X.
Voxel (i, j, k) spans [i, i+1] x [j, j+1] x [k, k+1] voxel units (S metres each).
"""
import io
import json
import math
import struct

import numpy as np
from PIL import Image

from voxlib import FACES, S, Vox, _hash, hexc, mir, quat_euler, xr  # noqa: F401


# ---------------------------------------------------------------- colours
def rgb_of(pal, c):
    seen = 0
    while not c.startswith('#'):
        c = pal[c]
        seen += 1
        if seen > 12:
            raise ValueError(c)
    return hexc(c)


def to_hex(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(v)))) for v in rgb)


def tone(pal, c, f):
    """Return a hex colour: palette colour c multiplied by f (f>1 lighter, f<1 darker)."""
    r, g, b = rgb_of(pal, c)
    if f >= 1.0:
        k = f - 1.0
        return to_hex((r + (255 - r) * k * 0.6, g + (255 - g) * k * 0.6, b + (255 - b) * k * 0.6))
    return to_hex((r * f, g * f, b * f))


def mix(pal, c1, c2, t):
    a, b = rgb_of(pal, c1), rgb_of(pal, c2)
    return to_hex([a[i] * (1 - t) + b[i] * t for i in range(3)])


# ---------------------------------------------------------------- voxel grid
class Vox2(Vox):
    def __init__(self):
        super().__init__()
        self.lids = []  # (x0, x1, y0, y1, z_plane, colour)

    def add_lid(self, x0, x1, y0, y1, z, colour):
        """Eyelid quad covering voxel columns [x0,x1) rows [y0,y1) on the front plane z."""
        self.lids.append((x0, x1, y0, y1, z, colour))

    def bone_box(self, bone):
        pts = [k for k, (c, b, j) in self.v.items() if b == bone]
        if not pts:
            return None
        a = np.array(pts)
        return a.min(0), a.max(0) + 1


# ---------------------------------------------------------------- rig
class Zone:
    """Soft-skinning zone: blends bone a (parent side) into bone b (child side) across a plane."""

    def __init__(self, a, b, axis, plane, hw, sign, fp):
        self.a, self.b, self.axis, self.plane, self.hw, self.sign, self.fp = a, b, axis, plane, hw, sign, fp

    def t(self, p):
        d = p[self.axis] - self.plane
        if abs(d) > self.hw + 1e-9:
            return None
        for ax, (lo, hi) in self.fp.items():
            if p[ax] < lo - 1e-9 or p[ax] > hi + 1e-9:
                return None
        return min(1.0, max(0.0, 0.5 + self.sign * d / (2 * self.hw)))


class Rig:
    def __init__(self, bones):
        self.bones = bones
        self.names = [b[0] for b in bones]
        self.index = {n: i for i, n in enumerate(self.names)}
        self.parent = {b[0]: b[1] for b in bones}
        self.pivot = {b[0]: np.array(b[2], float) for b in bones}
        self.zones = []
        self.zmap = {}
        self._wcache = {}
        self.boxes = {}

    def add_zone(self, vox, a, b, axis, plane, hw=1.0, sign=-1):
        """axis: 0/1/2 = x/y/z. sign: +1 when the child bone lies towards +axis."""
        box = vox.bone_box(b)
        if box is None:
            return
        lo, hi = box
        fp = {ax: (float(lo[ax]), float(hi[ax])) for ax in range(3) if ax != axis}
        z = Zone(a, b, axis, float(plane), hw, sign, fp)
        self.zones.append(z)
        self.zmap.setdefault(a, []).append(z)
        self.zmap.setdefault(b, []).append(z)

    def weights(self, p, owner):
        key = (p, owner)
        r = self._wcache.get(key)
        if r is not None:
            return r
        res = ((self.index[owner], 1.0),)
        for z in self.zmap.get(owner, ()):
            t = z.t(p)
            if t is not None:
                items = []
                if 1 - t > 1e-6:
                    items.append((self.index[z.a], round(1 - t, 4)))
                if t > 1e-6:
                    items.append((self.index[z.b], round(t, 4)))
                res = tuple(items)
                break
        self._wcache[key] = res
        return res

    # ------------------------------------------------ forward kinematics
    def fk(self, rots, hips_off, scales=None):
        """rots: bone -> quaternion; hips_off: metres. Returns bone -> 4x4 world matrix (metres)."""
        scales = scales or {}
        W = {}
        for n in self.names:
            p = self.parent[n]
            t = (self.pivot[n] - (self.pivot[p] if p else 0)) * S
            if n == 'Hips':
                t = t + np.asarray(hips_off)
            M = np.eye(4)
            M[:3, :3] = qmat(rots.get(n, (0, 0, 0, 1))) @ np.diag(scales.get(n, (1.0, 1.0, 1.0)))
            M[:3, 3] = t
            W[n] = (W[p] @ M) if p else M
        return W

    def min_y(self, rots, hips_off, bones=None, scales=None):
        W = self.fk(rots, hips_off, scales)
        lo = 1e9
        for n in (bones or [b for b in self.names if b != 'Skirt']):
            box = self.boxes.get(n)
            if box is None:
                continue
            (x0, y0, z0), (x1, y1, z1) = box
            for x in (x0, x1):
                for y in (y0, y1):
                    for z in (z0, z1):
                        q = (np.array([x, y, z]) - self.pivot[n]) * S
                        w = W[n] @ np.array([q[0], q[1], q[2], 1.0])
                        lo = min(lo, w[1])
        return lo


def qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


# ---------------------------------------------------------------- pose
class Pose:
    def __init__(self):
        self.r = {}
        self.off = [0.0, 0.0, 0.0]   # hips offset, voxel units
        self.blink = 0.0
        self.ground = 'feet'         # 'feet' | 'body' | None
        self.lift = 0.0              # extra height above the ground, voxel units

    def add(self, bone, x=0.0, y=0.0, z=0.0):
        a = self.r.get(bone, (0.0, 0.0, 0.0))
        self.r[bone] = (a[0] + x, a[1] + y, a[2] + z)

    def sym(self, part, x=0.0, y=0.0, z=0.0):
        """Apply to both sides; positive z means "outward" (away from the body) on both."""
        self.add('L' + part, x, y, z)
        self.add('R' + part, x, -y, -z)

    def get(self, bone):
        return self.r.get(bone, (0.0, 0.0, 0.0))


# ---------------------------------------------------------------- mesh
class Palette:
    def __init__(self):
        self.colors = {}

    def idx(self, rgb):
        return self.colors.setdefault(tuple(rgb), len(self.colors))

    def image(self):
        cell, per_row = 4, 64
        rows = (len(self.colors) + per_row - 1) // per_row
        hgt = 4
        while hgt < rows * cell:
            hgt *= 2
        img = Image.new('RGB', (per_row * cell, hgt), (255, 0, 255))
        px = img.load()
        for rgb, n in self.colors.items():
            cx, cy = (n % per_row) * cell, (n // per_row) * cell
            for a in range(cell):
                for b in range(cell):
                    px[cx + a, cy + b] = rgb
        self.size = img.size
        self.cell, self.per_row = cell, per_row
        return img

    def uv(self, n):
        cx = (n % self.per_row) * self.cell + self.cell / 2
        cy = (n // self.per_row) * self.cell + self.cell / 2
        return (cx / self.size[0], cy / self.size[1])


def build_mesh(vox, pal, rig, palette, jitter=0.012):
    pos, nrm, cid, jn, wt = [], [], [], [], []
    for (i, j, k), (c, b, jit) in vox.v.items():
        rgb = rgb_of(pal, c)
        if jit:
            lv = (_hash(i, j, k) % 5) - 2
            f = 1.0 + jitter * lv * jit
            rgb = tuple(max(0, min(255, int(round(x * f)))) for x in rgb)
        ci = palette.idx(rgb)
        for (dx, dy, dz), corners in FACES:
            nb = vox.v.get((i + dx, j + dy, k + dz))
            cw = [rig.weights((i + cx, j + cy, k + cz), b) for (cx, cy, cz) in corners]
            if nb is not None:
                nw = [rig.weights((i + cx, j + cy, k + cz), nb[1]) for (cx, cy, cz) in corners]
                if nw == cw:
                    continue
            for (cx, cy, cz), w in zip(corners, cw):
                pos.append(((i + cx) * S, (j + cy) * S, (k + cz) * S))
                nrm.append((dx, dy, dz))
                cid.append(ci)
                jn.append([a for a, _ in w] + [0] * (4 - len(w)))
                wt.append([b_ for _, b_ in w] + [0.0] * (4 - len(w)))
    n = len(pos)
    idx = np.zeros((n // 4) * 6, np.uint32)
    q = np.arange(n // 4, dtype=np.uint32) * 4
    idx[0::6], idx[1::6], idx[2::6], idx[3::6], idx[4::6], idx[5::6] = q, q + 1, q + 2, q, q + 2, q + 3
    return dict(pos=np.array(pos, np.float32), nrm=np.array(nrm, np.float32), cid=np.array(cid),
                jnt=np.array(jn, np.uint8), wgt=np.array(wt, np.float32), idx=idx)


# ---------------------------------------------------------------- GLB
class Blob:
    def __init__(self):
        self.data = bytearray()
        self.views, self.accs = [], []

    def view(self, data, target=None):
        while len(self.data) % 4:
            self.data.append(0)
        off = len(self.data)
        self.data.extend(data)
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
        if target:
            v['target'] = target
        self.views.append(v)
        return len(self.views) - 1

    def acc(self, arr, ctype, typ, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        a = {'bufferView': self.view(arr.tobytes(), target), 'componentType': ctype,
             'count': int(arr.shape[0]), 'type': typ}
        if minmax:
            flat = arr.reshape(arr.shape[0], -1)
            a['min'] = [float(x) for x in flat.min(0)]
            a['max'] = [float(x) for x in flat.max(0)]
        self.accs.append(a)
        return len(self.accs) - 1


def sample_clip(rig, clip, fps, base_hips, ground_bones):
    """Return times, per-bone quaternion arrays, hips translations (m) and blink weights."""
    name, dur, fn = clip
    nk = int(round(dur * fps)) + 1
    times = np.linspace(0, dur, nk).astype(np.float32)
    quats = {n: [] for n in rig.names}
    hips, blink, skirt_scale = [], [], []
    has_skirt = 'Skirt' in rig.index
    for t in times:
        p = fn(float(t))
        rots = {n: quat_euler(*p.r[n]) for n in p.r}
        for n in rig.names:
            quats[n].append(rots.get(n, np.array([0.0, 0.0, 0.0, 1.0])))
        off = np.array(p.off, float) * S
        if p.ground == 'feet':
            off[1] -= rig.min_y(rots, off, ground_bones)
        elif p.ground == 'body':
            off[1] -= rig.min_y(rots, off)
        off[1] += p.lift * S
        hips.append(base_hips + off)
        blink.append(p.blink)
        if has_skirt:
            # squash the skirt so that its hem never sinks below the ground (crouching, kneeling ...)
            def sc(sy):
                k = 1.0 + 0.5 * (1.0 - sy)
                return (k, sy, k)
            sy = 1.0
            if rig.min_y(rots, off, ['Skirt'], {'Skirt': sc(1.0)}) < 0:
                lo, hi = 0.3, 1.0
                if rig.min_y(rots, off, ['Skirt'], {'Skirt': sc(lo)}) >= 0:
                    for _ in range(14):
                        mid = (lo + hi) / 2
                        if rig.min_y(rots, off, ['Skirt'], {'Skirt': sc(mid)}) >= 0:
                            lo = mid
                        else:
                            hi = mid
                    sy = lo
                else:
                    sy = lo
            skirt_scale.append(sc(sy))
    for n in rig.names:
        q = np.array(quats[n], np.float32)
        for r in range(1, len(q)):
            if np.dot(q[r], q[r - 1]) < 0:
                q[r] = -q[r]
        quats[n] = q
    return times, quats, np.array(hips, np.float32), np.array(blink, np.float32), np.array(skirt_scale, np.float32)


def write_glb2(path, name, vox, pal, rig, clips, fps=30, roughness=0.8):
    for n in rig.names:
        rig.boxes[n] = None
        b = vox.bone_box(n)
        if b is not None:
            rig.boxes[n] = (tuple(float(x) for x in b[0]), tuple(float(x) for x in b[1]))
    palette = Palette()
    body = build_mesh(vox, pal, rig, palette)

    # eyelids: skinned to the head, hidden inside the face until the Blink morph pushes them out
    lids = None
    if vox.lids:
        lp, ln, lc, lj, lw, ld = [], [], [], [], [], []
        head = rig.index['Head']
        for li_, (x0, x1, y0, y1, z, colour) in enumerate(vox.lids):
            ci = palette.idx(rgb_of(pal, colour))
            e = 0.04  # slightly larger than the eye so no hairline of the lash shows around the lid
            bias = 0.012 * (li_ % 2)  # the lash row sits a hair in front of the skin row (no z-fighting)
            for (cx, cy) in ((x0 - e, y0 - e), (x1 + e, y0 - e), (x1 + e, y1 + e), (x0 - e, y1 + e)):
                lp.append((cx * S, cy * S, (z - 0.62 + bias) * S))
                ld.append((0.0, 0.0, 0.68 * S))
                ln.append((0, 0, 1))
                lc.append(ci)
                lj.append([head, 0, 0, 0])
                lw.append([1.0, 0, 0, 0])
        nq = len(lp) // 4
        li = np.zeros(nq * 6, np.uint32)
        q = np.arange(nq, dtype=np.uint32) * 4
        li[0::6], li[1::6], li[2::6], li[3::6], li[4::6], li[5::6] = q, q + 1, q + 2, q, q + 2, q + 3
        lids = dict(pos=np.array(lp, np.float32), nrm=np.array(ln, np.float32), cid=np.array(lc),
                    jnt=np.array(lj, np.uint8), wgt=np.array(lw, np.float32), idx=li,
                    delta=np.array(ld, np.float32))

    img = palette.image()
    B = Blob()

    def prim(m, delta=None):
        uv = np.array([palette.uv(n) for n in m['cid']], np.float32)
        a = {'POSITION': B.acc(m['pos'], 5126, 'VEC3', 34962, True),
             'NORMAL': B.acc(m['nrm'], 5126, 'VEC3', 34962),
             'TEXCOORD_0': B.acc(uv, 5126, 'VEC2', 34962),
             'JOINTS_0': B.acc(m['jnt'], 5121, 'VEC4', 34962),
             'WEIGHTS_0': B.acc(m['wgt'], 5126, 'VEC4', 34962)}
        ix = m['idx'].astype(np.uint16) if len(m['pos']) < 65536 else m['idx']
        p = {'attributes': a, 'indices': B.acc(ix, 5123 if ix.dtype == np.uint16 else 5125, 'SCALAR', 34963),
             'material': 0}
        if delta is not None:
            p['targets'] = [{'POSITION': B.acc(delta, 5126, 'VEC3', 34962, True)}]
        return p

    meshes = [{'name': name + '_Skin', 'primitives': [prim(body)]}]
    if lids:
        meshes.append({'name': name + '_Lids', 'primitives': [prim(lids, lids['delta'])],
                       'weights': [0.0], 'extras': {'targetNames': ['Blink']}})

    # skeleton
    ibm = []
    for bn in rig.names:
        m = np.eye(4, dtype=np.float32)
        m[:3, 3] = -rig.pivot[bn] * S
        ibm.append(m.T.reshape(16))
    a_ibm = B.acc(np.array(ibm, np.float32), 5126, 'MAT4')
    png = io.BytesIO()
    img.save(png, 'PNG')
    bv_img = B.view(png.getvalue())

    nodes = []
    for bn in rig.names:
        p = rig.parent[bn]
        t = (rig.pivot[bn] - (rig.pivot[p] if p else 0)) * S
        nd = {'name': bn, 'translation': [float(x) for x in t]}
        ch = [rig.index[c] for c in rig.names if rig.parent[c] == bn]
        if ch:
            nd['children'] = ch
        nodes.append(nd)
    mesh_node = len(nodes)
    nodes.append({'name': name + '_Skin', 'mesh': 0, 'skin': 0})
    kids = [mesh_node]
    lid_node = None
    if lids:
        lid_node = len(nodes)
        nodes.append({'name': name + '_Lids', 'mesh': 1, 'skin': 0})
        kids.append(lid_node)
    kids.append(rig.index['Root'])
    root_node = len(nodes)
    nodes.append({'name': name, 'children': kids})

    base_hips = (rig.pivot['Hips'] - rig.pivot['Root']) * S
    ground_bones = [n for n in rig.names if n.endswith('Foot')]
    anims = []
    for clip in clips:
        times, quats, hips, blink, skirt_scale = sample_clip(rig, clip, fps, base_hips, ground_bones)
        a_t = B.acc(times.reshape(-1, 1), 5126, 'SCALAR', minmax=True)
        samplers, chans = [], []
        for bn in rig.names:
            a_o = B.acc(quats[bn], 5126, 'VEC4')
            samplers.append({'input': a_t, 'output': a_o, 'interpolation': 'LINEAR'})
            chans.append({'sampler': len(samplers) - 1, 'target': {'node': rig.index[bn], 'path': 'rotation'}})
        a_o = B.acc(hips, 5126, 'VEC3')
        samplers.append({'input': a_t, 'output': a_o, 'interpolation': 'LINEAR'})
        chans.append({'sampler': len(samplers) - 1, 'target': {'node': rig.index['Hips'], 'path': 'translation'}})
        if len(skirt_scale):
            a_o = B.acc(skirt_scale, 5126, 'VEC3')
            samplers.append({'input': a_t, 'output': a_o, 'interpolation': 'LINEAR'})
            chans.append({'sampler': len(samplers) - 1, 'target': {'node': rig.index['Skirt'], 'path': 'scale'}})
        if lid_node is not None:
            a_o = B.acc(blink.reshape(-1, 1), 5126, 'SCALAR')
            samplers.append({'input': a_t, 'output': a_o, 'interpolation': 'LINEAR'})
            chans.append({'sampler': len(samplers) - 1, 'target': {'node': lid_node, 'path': 'weights'}})
        anims.append({'name': clip[0], 'samplers': samplers, 'channels': chans})

    gltf = {
        'asset': {'version': '2.0', 'generator': 'GLBmodel vox2'},
        'scene': 0,
        'scenes': [{'name': 'Scene', 'nodes': [root_node]}],
        'nodes': nodes, 'meshes': meshes,
        'skins': [{'name': name + '_Rig', 'inverseBindMatrices': a_ibm,
                   'joints': list(range(len(rig.names))), 'skeleton': rig.index['Root']}],
        'materials': [{'name': name, 'pbrMetallicRoughness': {
            'baseColorTexture': {'index': 0}, 'metallicFactor': 0.0, 'roughnessFactor': roughness}}],
        'textures': [{'sampler': 0, 'source': 0}],
        'images': [{'name': name + '_Palette', 'mimeType': 'image/png', 'bufferView': bv_img}],
        'samplers': [{'magFilter': 9728, 'minFilter': 9728, 'wrapS': 33071, 'wrapT': 33071}],
        'animations': anims, 'accessors': B.accs, 'bufferViews': B.views,
        'buffers': [{'byteLength': 0}],
    }
    blob = B.data
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
    return dict(verts=len(body['pos']), tris=len(body['idx']) // 3, voxels=len(vox.v),
                colors=len(palette.colors), clips=len(anims), kb=total // 1024)
