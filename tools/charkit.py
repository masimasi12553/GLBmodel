"""Shared character construction kit for the v2 voxel villagers (body, face, hair, garments)."""
import numpy as np

from vox2 import Rig, Vox2, mir, mix, rgb_of, tone, xr  # noqa: F401

DIMS = {
    'man':   dict(L=24, K=13, TH=14, H=14, tw=5, ua=7, la=5),
    'woman': dict(L=21, K=11, TH=13, H=14, tw=5, ua=7, la=5),
    'kid':   dict(L=13, K=7, TH=9, H=13, tw=5, ua=5, la=4),
}

BASE_PAL = {'eye_white': '#f1eddf', 'lash': '#241a16', 'sole': '#2b2018'}

SIDES = ('L', 'R')


class Char:
    """A voxel character on a fixed skeleton (Root/Hips/Spine/Chest/Neck/Head + limbs)."""

    def __init__(self, name, kind, pal, **over):
        self.name = name
        self.kind = kind
        self.d = dict(DIMS[kind])
        self.d.update(over)
        self.pal = dict(BASE_PAL)
        self.pal.update(pal)
        self.pal.setdefault('skin_dk', tone(self.pal, 'skin', 0.9))
        self.pal.setdefault('skin_lt', tone(self.pal, 'skin', 1.06))
        d = self.d
        d['T'] = d['L'] + 3 + d['TH']          # neck row
        d['hy'] = d['T'] + 1                   # bottom row of the head
        d['cy'] = d['L'] + 3 + d['TH'] // 2    # Spine / Chest boundary
        d['ytop'] = d['hy'] + d['H'] - 1       # top skull row
        self.m = Vox2()
        self.extra_bones = []
        self.tails = []          # (bone, gain): hair / cloth that follows head motion
        self.zone_pairs = []     # (parent, child, plane_y) soft-skinning zones between chain bones
        self.has_skirt = False
        self.eye_boxes = []
        self.mannequin()

    # ------------------------------------------------------------ colours
    def t(self, c, f):
        return tone(self.pal, c, f)

    def mix(self, a, b, k):
        return mix(self.pal, a, b, k)

    # ------------------------------------------------------------ skeleton
    def bones(self):
        d = self.d
        L, T, hy, tw = d['L'], d['T'], d['hy'], d['tw']
        zc = -0.5
        b = [('Root', None, (0, 0, zc)),
             ('Hips', 'Root', (0, L + 1.5, zc)),
             ('Spine', 'Hips', (0, L + 3, zc)),
             ('Chest', 'Spine', (0, d['cy'], zc)),
             ('Neck', 'Chest', (0, T, zc)),
             ('Head', 'Neck', (0, hy, zc))]
        ax = tw + 1.5
        for s in SIDES:
            g = 1 if s == 'L' else -1
            b += [(s + 'UpperArm', 'Chest', (g * ax, T - 1.5, zc)),
                  (s + 'LowerArm', s + 'UpperArm', (g * ax, T - d['ua'], zc)),
                  (s + 'Hand', s + 'LowerArm', (g * ax, T - d['ua'] - d['la'], zc))]
        for s in SIDES:
            g = 1 if s == 'L' else -1
            b += [(s + 'Thigh', 'Hips', (g * 3, L, zc)),
                  (s + 'Shin', s + 'Thigh', (g * 3, d['K'], zc)),
                  (s + 'Foot', s + 'Shin', (g * 3, 3, zc))]
        return b + self.extra_bones

    def rig(self):
        d = self.d
        L, K, T, hy = d['L'], d['K'], d['T'], d['hy']
        r = Rig(self.bones())
        m = self.m
        r.add_zone(m, 'Hips', 'Spine', 1, L + 3, 1.0)
        r.add_zone(m, 'Spine', 'Chest', 1, d['cy'], 1.0)
        r.add_zone(m, 'Chest', 'Neck', 1, T, 0.5)
        r.add_zone(m, 'Neck', 'Head', 1, hy, 0.5)
        for s in SIDES:
            r.add_zone(m, 'Hips', s + 'Thigh', 1, L, 1.0)
            r.add_zone(m, s + 'Thigh', s + 'Shin', 1, K, 1.0)
            r.add_zone(m, s + 'Shin', s + 'Foot', 1, 3, 0.5)
            r.add_zone(m, s + 'UpperArm', s + 'LowerArm', 1, T - d['ua'], 1.0)
            r.add_zone(m, s + 'LowerArm', s + 'Hand', 1, T - d['ua'] - d['la'], 0.6)
        for par, bn, plane in self.zone_pairs:
            r.add_zone(m, par, bn, 1, plane, 0.8)
        return r

    # ------------------------------------------------------------ mannequin
    def mannequin(self):
        d, m = self.d, self.m
        L, K, T, hy, H, tw = d['L'], d['K'], d['T'], d['hy'], d['H'], d['tw']
        for s in SIDES:
            x0, x1 = xr(s, 1, 5)
            m.box(x0, x1, 3, K, -2, 2, 'skin', s + 'Shin', 0.5)
            m.box(x0, x1, K, L, -2, 2, 'skin', s + 'Thigh', 0.5)
            m.box(x0, x1, 0, 3, -2, 3, 'skin', s + 'Foot', 0.5)
        m.box(-tw, tw, L, L + 3, -3, 3, 'skin', 'Hips', 0.5)
        for y in range(L + 3, T):
            m.box(-tw, tw, y, y + 1, -3, 3, 'skin', self.tb(y), 0.5)
        for x in (-tw, tw - 1):
            for z in (-3, 2):
                m.rm(x, T - 1, z)
        m.box(-2, 2, T, T + 1, -2, 2, 'skin_dk', 'Neck', 0.3)
        m.box(-7, 7, hy, hy + H, -6, 6, 'skin', 'Head', 0.3)
        for x in range(-7, 7):
            m.rm(x, hy, -6)
        for z in range(-6, 6):
            m.rm(-7, hy, z)
            m.rm(6, hy, z)
        ua, la = d['ua'], d['la']
        for s in SIDES:
            x0, x1 = xr(s, tw, tw + 3)
            m.box(x0, x1, T - ua, T, -2, 1, 'skin', s + 'UpperArm', 0.5)
            m.box(x0, x1, T - ua - la, T - ua, -2, 1, 'skin', s + 'LowerArm', 0.5)
            m.box(x0, x1, T - ua - la - 3, T - ua - la, -2, 1, 'skin', s + 'Hand', 0.3)
            xo = x1 - 1 if s == 'L' else x0
            m.rm(xo, T - 1, -2)
            m.rm(xo, T - 1, 0)

    def tb(self, y):
        d = self.d
        if y < d['L'] + 3:
            return 'Hips'
        return 'Spine' if y < d['cy'] else 'Chest'

    # ------------------------------------------------------------ painting helpers
    def paint_where(self, pred, colour, jit=None):
        m = self.m
        for (x, y, z), (c, b, j) in list(m.v.items()):
            if pred(x, y, z, b, c):
                m.v[(x, y, z)] = (colour, b, j if jit is None else jit)

    def ov(self, x, y, z, colour, jit=1.0, bone=None):
        """Add an overlay voxel on the torso (bone chosen from the row)."""
        self.m.put(x, y, z, colour, bone or self.tb(y), jit)

    def rect(self, x0, x1, y0, y1, z, colour, jit=1.0, put=False, bone=None):
        """Paint (or add) a rectangle on the plane z. Ranges are half open."""
        for x in range(x0, x1):
            for y in range(y0, y1):
                if put:
                    self.ov(x, y, z, colour, jit, bone)
                else:
                    self.m.paint(x, y, z, colour, jit)

    # ------------------------------------------------------------ garments
    def legs(self, pants, shoe, boot_top=6, rim_f=1.2, toe_f=1.14):
        m, d = self.m, self.d
        L, K = d['L'], d['K']
        for s in SIDES:
            outer = 4 if s == 'L' else -5
            for (x, y, z), (col, b, j) in list(m.v.items()):
                if b in (s + 'Thigh', s + 'Shin'):
                    if b == s + 'Shin' and y < boot_top:
                        m.v[(x, y, z)] = (self.t(shoe, rim_f if y == boot_top - 1 else 1.0), b, 1.0)
                    else:
                        f = 0.94 if x == outer else 1.0
                        if y == K and z == 1:
                            f *= 0.92
                        m.v[(x, y, z)] = (self.t(pants, f), b, 1.0)
                elif b == s + 'Foot':
                    if y == 0:
                        m.v[(x, y, z)] = ('sole', b, 0.5)
                    else:
                        f = toe_f if z == 2 else (0.9 if z == -2 else 1.0)
                        m.v[(x, y, z)] = (self.t(shoe, f), b, 1.0)
            x0, x1 = xr(s, 1, 5)
            for x in (x0, x1 - 1):
                m.rm(x, 2, 2)
        for y in (L, L + 1):
            self.paint_where(lambda x, yy, z, b, c, y=y: b == 'Hips' and yy == y, pants, 1.0)

    def torso_paint(self, colour, y0=None, y1=None, jit=1.0):
        d = self.d
        y0 = d['L'] + 3 if y0 is None else y0
        y1 = d['T'] if y1 is None else y1
        self.paint_where(lambda x, y, z, b, c: b in ('Hips', 'Spine', 'Chest') and y0 <= y < y1, colour, jit)

    def arms_paint(self, upper=None, lower=None, hand=None, upper_rows=None, cuff=None, jit=1.0):
        """upper / lower / hand: colours (None keeps skin). upper_rows=(a, b): only rows a..b below the shoulder."""
        m, d = self.m, self.d
        T = d['T']
        y_end = T - d['ua'] - d['la']
        for s in SIDES:
            for (x, y, z), (col, b, j) in list(m.v.items()):
                if b == s + 'UpperArm' and upper:
                    if upper_rows is None or (T - upper_rows[1] <= y < T - upper_rows[0]):
                        m.v[(x, y, z)] = (upper, b, jit)
                elif b == s + 'LowerArm' and lower:
                    m.v[(x, y, z)] = (lower, b, jit)
                elif b == s + 'Hand' and hand:
                    m.v[(x, y, z)] = (hand, b, jit)
            if cuff:
                col, rows = cuff
                for (x, y, z), (c0, b, j) in list(m.v.items()):
                    if b == s + 'LowerArm' and y_end <= y < y_end + rows:
                        m.v[(x, y, z)] = (col, b, jit)

    def belt(self, y, colour='belt', buckle='metal'):
        self.paint_where(lambda x, yy, z, b, c: b in ('Hips', 'Spine', 'Chest') and yy == y, colour, 1.0)
        for x in (-1, 0):
            self.m.put(x, y, 3, buckle, self.tb(y), 0)
            self.m.put(x, y - 1, 3, buckle, self.tb(y - 1), 0)

    def skirt(self, ytop, ybot, top_half, bot_half, colour, trim=None, trim_rows=1, cham=3, fold=True):
        """Hollow bell-shaped skirt (one voxel thick) attached to the hips.

        Each row is a rounded rectangle with integer half sizes (top_half -> bot_half = (half width, half depth)),
        so the outline widens in clean steps.
        """
        m = self.m
        if not self.has_skirt:
            self.extra_bones.append(('Skirt', 'Hips', (0, ytop + 1, -0.5)))
        self.has_skirt = True

        def ring(a, b):
            cells = set()
            for x in range(-a, a):
                for z in range(-b, b):
                    u = min(x + a, a - 1 - x)          # distance to the nearest x edge
                    w = min(z + b, b - 1 - z)
                    if u + w < cham - 1:
                        continue                        # chamfered corner
                    cells.add((x, z))
            return cells
        for y in range(ybot, ytop + 1):
            tt = (ytop - y) / max(1, ytop - ybot)
            a = int(round(top_half[0] + (bot_half[0] - top_half[0]) * tt))
            b = int(round(top_half[1] + (bot_half[1] - top_half[1]) * tt))
            shell = ring(a, b) - ring(a - 1, b - 1)
            for (x, z) in shell:
                f = 1.0
                if fold:
                    key = x if (z in (-b, b - 1)) else z
                    if key % 3 == 0:
                        f = 0.94
                col = trim if (trim and y < ybot + trim_rows) else self.t(colour, f)
                m.put(x, y, z, col, 'Skirt', 1.0)

    # ------------------------------------------------------------ face
    def face(self, eye_row=None, iris='iris', brow=('hair', 3, 1), nose=2, mouth=None,
             gap=4, eye_w=2):
        """Small restrained face (no blush, mouth optional). eye_row: y offset (from hy) of the lower eye row."""
        d, m = self.d, self.m
        hy = d['hy']
        er = eye_row if eye_row is not None else (6 if self.kind != 'kid' else 5)
        ey = hy + er
        half = gap // 2
        self.eye_boxes = []
        for s in SIDES:
            for c in range(eye_w):           # c = 0 is the inner voxel
                x = half + c if s == 'L' else mir(half + c)
                m.paint(x, ey, 5, iris if c == 0 else 'eye_white', 0)
                m.paint(x, ey + 1, 5, 'lash', 0)
            x0, x1 = (half, half + eye_w) if s == 'L' else (-half - eye_w, -half)
            self.eye_boxes.append((x0, x1, ey, ey + 2))
            bc, bw, bt = brow
            if bc:
                off = 1 if bw > eye_w else 0
                for c in range(bw):
                    xl = half + c - off
                    x = xl if s == 'L' else mir(xl)
                    m.paint(x, ey + 3, 5, bc, 0)
                    if bt > 1 and c < 2:
                        m.paint(x, ey + 4, 5, bc, 0)
        if nose:
            for x in (-1, 0):
                m.put(x, ey - 2, 6, 'skin_dk', 'Head', 0)
                if nose > 1:
                    m.put(x, ey - 1, 6, 'skin', 'Head', 0)
        self.eye_y = ey
        self.mouth_y = ey - 4
        if mouth:
            for c in range(mouth):
                m.paint(-mouth // 2 + c, self.mouth_y, 5, 'mouth', 0)
        for (x0, x1, y0, y1) in self.eye_boxes:      # eyelids for the Blink morph
            m.add_lid(x0, x1, y0 + 1, y1, 6, 'skin')
            m.add_lid(x0, x1, y0, y0 + 1, 6, 'lash')

    def ears(self, rows=None):
        m, hy = self.m, self.d['hy']
        rows = rows or ((4, 5, 6) if self.kind != 'kid' else (3, 4, 5))
        for x in (-8, 7):
            for r in rows:
                for z in (0, 1):
                    m.put(x, hy + r, z, 'skin', 'Head', 0.3)

    # ------------------------------------------------------------ hair
    def hair(self, color='hair', side_bottom=6, back_bottom=3, bangs=None, top_layers=2,
             crown_rows=3, sideburn=None, tufts=(), shell=True, cut=(), shade=True):
        """Rounded hair cap. bangs: 16 lengths for x = -8..7 (rows hanging in front of the forehead)."""
        m, d = self.m, self.d
        hy, ytop = d['hy'], d['ytop']
        cells = set()
        for y in range(ytop - crown_rows + 1, ytop + 1):
            for x in range(-7, 7):
                for z in range(-6, 5):
                    cells.add((x, y, z))
        ext = [(8, 7, 3.2), (7, 6, 3.2), (5, 4, 3.0), (3, 2, 3.0)]
        for k in range(1, top_layers + 1):
            ax, bz, p = ext[k - 1]
            for x in range(-ax, ax):
                for z in range(-bz, bz):
                    if (abs(x + 0.5) / ax) ** p + (abs(z + 0.5) / bz) ** p <= 1.0:
                        cells.add((x, ytop + k, z))
        if shell:
            for y in range(hy + side_bottom, ytop + 1):
                for z in range(-7, 5):
                    cells.add((-8, y, z))
                    cells.add((7, y, z))
                    if z >= -6:
                        cells.add((-7, y, z))
                        cells.add((6, y, z))
            for y in range(hy + back_bottom, ytop + 1):
                for x in range(-8, 8):
                    cells.add((x, y, -7))
                    if -7 <= x <= 6:
                        cells.add((x, y, -6))
        if sideburn is not None:
            for y in range(hy + sideburn, ytop + 1):
                for z in (3, 4, 5):
                    for x in (-8, -7, 6, 7):
                        cells.add((x, y, z))
        if bangs is None:
            bangs = [2] * 16
        for i, ln in enumerate(bangs):
            x = i - 8
            for r in range(ln):
                y = ytop - r
                cells.add((x, y, 5))
                if r < ln - 1:
                    cells.add((x, y, 6))
        for (x, k, z) in tufts:
            cells.add((x, ytop + k, z))
        for c_ in cut:
            cells.discard(c_)
        for (x, y, z) in cells:
            f = 1.0
            if shade:
                f = (0.9, 0.96, 1.0, 1.05)[(x * 7 + (z // 2) * 13 + 5) % 4]
                if y > ytop:
                    f *= 1.1
                elif y >= ytop - 1 and z < 5:
                    f *= 1.04
                if y < hy + 5:
                    f *= 0.9
            col = self.t(color, f)
            if (x, y, z) in m.v:
                m.paint(x, y, z, col, 1.0)
            else:
                m.put(x, y, z, col, 'Head', 1.0)
        return cells

    def tail_chain(self, prefix, parent, pivots, segs, gain=1.0):
        """Bone chain hanging off `parent` (pigtail, braid, scarf end). segs: per bone [(x0,x1,y0,y1,z0,z1,colour)]."""
        names, par = [], parent
        for n, (pv, boxes) in enumerate(zip(pivots, segs)):
            bn = '%s%d' % (prefix, n + 1)
            self.extra_bones.append((bn, par, pv))
            if n > 0:
                self.zone_pairs.append((par, bn, pv[1]))
            for (x0, x1, y0, y1, z0, z1, col) in boxes:
                self.m.box(x0, x1, y0, y1, z0, z1, col, bn, 1.0)
            par = bn
            names.append(bn)
        for i, bn in enumerate(names):
            self.tails.append((bn, gain * (1 - 0.3 * i)))
        return names

    # ------------------------------------------------------------ export
    def export(self, path, clips):
        from vox2 import write_glb2
        return write_glb2(path, self.name, self.m, self.pal, self.rig(), clips)
