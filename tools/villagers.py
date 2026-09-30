#!/usr/bin/env python3
"""Generate the voxel villager GLB models (heroine.glb style).

usage: python3 tools/villagers.py [out_dir]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from voxlib import Vox, write_glb, xr, mir  # noqa: E402

SIDES = ('L', 'R')

# ---------------------------------------------------------------- body
BODY = {
    'man':   dict(L=24, knee=13, TH=14, H=14, tw=5, ua=7, la=5),
    'woman': dict(L=22, knee=12, TH=13, H=14, tw=5, ua=7, la=5),
    'kid':   dict(L=13, knee=7, TH=9, H=13, tw=5, ua=5, la=4),
}


class Char:
    def __init__(self, name, body, pal):
        self.name = name
        self.P = dict(BODY[body])
        self.kind = body
        self.pal = dict(BASE_PAL)
        self.pal.update(pal)
        self.m = Vox()
        P = self.P
        P['T'] = P['L'] + 3 + P['TH']
        P['hy'] = P['T'] + 1
        P['cy'] = P['L'] + 3 + P['TH'] // 2  # chest bone start
        self.extra_bones = []
        self.tails = []  # (bone, sway gain)
        self.has_skirt = False
        self.base()

    # bone for a torso voxel row
    def tb(self, y):
        P = self.P
        if y < P['L'] + 3:
            return 'Hips'
        return 'Spine' if y < P['cy'] else 'Chest'

    def bones(self):
        P = self.P
        L, T, hy, tw = P['L'], P['T'], P['hy'], P['tw']
        ax = tw + 1.5
        b = [('Root', None, (0, 0, 0)),
             ('Hips', 'Root', (0, L + 1.5, 0)),
             ('Spine', 'Hips', (0, L + 3, 0)),
             ('Chest', 'Spine', (0, P['cy'], 0)),
             ('Neck', 'Chest', (0, T, 0)),
             ('Head', 'Neck', (0, hy, 0))]
        for s in SIDES:
            g = 1 if s == 'L' else -1
            b += [(s + 'UpperArm', 'Chest', (g * ax, T - 1.5, -0.5)),
                  (s + 'LowerArm', s + 'UpperArm', (g * ax, T - P['ua'], -0.5)),
                  (s + 'Hand', s + 'LowerArm', (g * ax, T - P['ua'] - P['la'], -0.5))]
        for s in SIDES:
            g = 1 if s == 'L' else -1
            b += [(s + 'Thigh', 'Hips', (g * 3, L, 0)),
                  (s + 'Shin', s + 'Thigh', (g * 3, P['knee'], 0)),
                  (s + 'Foot', s + 'Shin', (g * 3, 3, 0))]
        return b + self.extra_bones

    def base(self):
        m, P = self.m, self.P
        L, K, T, hy, H, tw = P['L'], P['knee'], P['T'], P['hy'], P['H'], P['tw']
        for s in SIDES:
            x0, x1 = xr(s, 1, 5)
            m.box(x0, x1, 3, K, -2, 2, 'shin', s + 'Shin')
            m.box(x0, x1, K, L, -2, 2, 'thigh', s + 'Thigh')
            m.box(x0, x1, 1, 3, -2, 3, 'shoe', s + 'Foot')
            m.box(x0, x1, 0, 1, -2, 3, 'sole', s + 'Foot')
            m.box(x0, x1, 3, 4, -2, 2, 'shoe', s + 'Foot')  # boot collar
            # round toe
            for x in (x0, x1 - 1):
                m.rm(x, 2, 2)
        m.box(-tw, tw, L, L + 3, -3, 3, 'pants', 'Hips')
        for y in range(L + 3, T):
            m.box(-tw, tw, y, y + 1, -3, 3, 'shirt', self.tb(y))
        # shoulders rounded
        for x in (-tw, tw - 1):
            for z in (-3, 2):
                m.rm(x, T - 1, z)
        m.box(-2, 2, T, T + 1, -2, 2, 'skin', 'Neck', 0)
        m.box(-7, 7, hy, hy + H, -6, 6, 'skin', 'Head', 0)
        for x in range(-7, 7):
            m.rm(x, hy, -6)
        for z in range(-6, 6):
            m.rm(-7, hy, z)
            m.rm(6, hy, z)
        ua, la = P['ua'], P['la']
        for s in SIDES:
            x0, x1 = xr(s, tw, tw + 3)
            m.box(x0, x1, T - ua, T, -2, 1, 'sleeve_u', s + 'UpperArm')
            m.box(x0, x1, T - ua - la, T - ua, -2, 1, 'sleeve_l', s + 'LowerArm')
            m.box(x0, x1, T - ua - la - 3, T - ua - la, -2, 1, 'skin', s + 'Hand', 0)
            xo = x1 - 1 if s == 'L' else x0
            m.rm(xo, T - 1, -2)
            m.rm(xo, T - 1, 0)

    # ------------------------------------------------------------ face / hair
    def face(self, eye='adult', blush=False, mouth='MM', brow=True, eye_top=None, lashes=False):
        m, hy = self.m, self.P['hy']
        pats = {
            # rows top->bottom, columns outer->inner
            'adult': ['KK', 'ED', 'ED'],
            'small': ['KK', 'ID', 'ID'],
            'soft': ['KKK', 'IWD', 'IDD', 'LLI'],
            'kid': ['KKK', 'DWD', 'IDI', 'LLL'],
        }
        pat = pats[eye]
        top = eye_top if eye_top is not None else hy + (6 if eye in ('adult', 'small') else 7)
        if self.kind == 'kid' and eye_top is None:
            top = hy + 6
        cmap = {'K': 'lash', 'E': 'eye_white', 'D': 'pupil', 'I': 'iris', 'L': 'iris_lt', 'W': 'hilite'}
        for side in SIDES:
            for r, row in enumerate(pat):
                for c, ch in enumerate(row):
                    if ch == '.':
                        continue
                    x = -5 + c
                    if side == 'L':
                        x = mir(x)
                    m.paint(x, top - r, 5, cmap[ch], 0)
            xo = -6 if side == 'R' else 5
            if lashes:
                m.paint(xo, top, 5, 'lash', 0)
                m.paint(xo, top - 1, 5, 'lash', 0)
            if brow:
                bw = len(pat[0])
                for c in range(bw):
                    x = -5 + c
                    m.paint(x if side == 'R' else mir(x), top + 2, 5, 'brow', 0)
            if blush:
                bx = (-6, -5) if side == 'R' else (4, 5)
                for x in bx:
                    m.paint(x, top - len(pat), 5, 'blush', 0)
        my = top - len(pat) - (2 if self.kind != 'kid' else 1)
        w = len(mouth)
        for c, ch in enumerate(mouth):
            if ch != '.':
                m.paint(-w // 2 + c, my, 5, 'mouth' if ch == 'M' else 'mouth_dk', 0)
        self.mouth_y = my

    def hair(self, side_bottom=7, back_bottom=4, bangs=None, color='hair', ears=True, sideburn=True):
        m, P = self.m, self.P
        hy, H = P['hy'], P['H']
        top = hy + H
        for x in range(-8, 8):
            for z in range(-7, 7):
                m.put(x, top, z, color, 'Head')
        for x in range(-7, 7):
            for z in range(-6, 6):
                m.put(x, top + 1, z, color, 'Head')
        for z in range(-7, 6):
            for y in range(hy + side_bottom, top):
                m.put(-8, y, z, color, 'Head')
                m.put(7, y, z, color, 'Head')
        for x in range(-8, 8):
            for y in range(hy + back_bottom, top):
                m.put(x, y, -7, color, 'Head')
        if sideburn and side_bottom > 4:
            for z in (2, 3, 4):
                for y in range(hy + 4, hy + side_bottom):
                    m.put(-8, y, z, color, 'Head')
                    m.put(7, y, z, color, 'Head')
        if bangs is None:
            bangs = [2] * 16
        for c, ln in enumerate(bangs):
            x = c - 8
            for d in range(ln):
                m.put(x, top - 1 - d, 6, color, 'Head')
            for d in range(ln + 1):
                m.paint(x, top - 1 - d, 5, color)
        # round top corners
        for x in (-8, 7):
            m.rm(x, top, -7)
            m.rm(x, top, 6)
        if ears:
            for s in SIDES:
                x = -8 if s == 'R' else 7
                for y in (hy + 4, hy + 5, hy + 6):
                    if y < hy + side_bottom and m.get(x, y, 1) is None:
                        m.put(x, y, 1, 'skin', 'Head', 0)
                        m.put(x, y, 0, 'skin', 'Head', 0)

    # ------------------------------------------------------------ clothing helpers
    def belt(self, y, color='belt', buckle='metal', tw=None):
        m, P = self.m, self.P
        tw = tw or P['tw']
        m.pbox(-tw - 2, tw + 2, y, y + 1, -8, 8, color)
        m.put(-1, y, 3, buckle, self.tb(y), 0)
        m.put(0, y, 3, buckle, self.tb(y), 0)

    def skirt(self, ytop, ybot, hx0, hx1, hz0, hz1, color, hem=None, hem_rows=1):
        m = self.m
        self.has_skirt = True
        for y in range(ybot, ytop):
            t = (ytop - 1 - y) / max(1, ytop - 1 - ybot)
            hx = int(round(hx0 + (hx1 - hx0) * t))
            hz = int(round(hz0 + (hz1 - hz0) * t))
            c = hem if (hem and y < ybot + hem_rows) else color
            for x in range(-hx, hx):
                for z in range(-hz, hz):
                    edge = x in (-hx, hx - 1) or z in (-hz, hz - 1)
                    corner = x in (-hx, hx - 1) and z in (-hz, hz - 1)
                    if edge and not corner:
                        m.put(x, y, z, c, 'Hips')
        return

    def tail_chain(self, prefix, parent, pivots, segs):
        """segs: list of lists of (x0,x1,y0,y1,z0,z1,color) per bone."""
        names = []
        par = parent
        for n, (pv, boxes) in enumerate(zip(pivots, segs)):
            bn = '%s%d' % (prefix, n + 1)
            self.extra_bones.append((bn, par, pv))
            for (x0, x1, y0, y1, z0, z1, c) in boxes:
                self.m.box(x0, x1, y0, y1, z0, z1, c, bn)
            par = bn
            names.append(bn)
        return names


BASE_PAL = {
    'eye_white': '#f1eddf', 'pupil': '#2a2320', 'lash': '#231a17', 'hilite': '#ffffff',
    'iris': '#6b4a30', 'iris_lt': '#9a7550', 'blush': '#f19a93', 'mouth_dk': '#5a2a24',
    'thigh': 'pants', 'shin': 'pants', 'sleeve_u': 'shirt', 'sleeve_l': 'shirt',
    'sole': '#2e2219', 'brow': 'hair',
}


# ---------------------------------------------------------------- characters
def villager():
    c = Char('villager', 'man', {
        'shirt': '#e2d5b4', 'skin': '#e8b89a', 'pants': '#7d6a51', 'shoe': '#4b3827',
        'hair': '#6b4a2e', 'mouth': '#955742', 'vest': '#8f5c39', 'belt': '#5d4130',
        'metal': '#aa8e4b', 'scarf': '#a8562f', 'iris': '#5b3d26',
        'sleeve_l': 'skin', 'cuff': '#d3c5a2',
    })
    m, P = c.m, c.P
    L, T, tw = P['L'], P['T'], P['tw']
    # rolled sleeves: forearm skin with a cuff on top
    for s in SIDES:
        x0, x1 = xr(s, tw, tw + 3)
        m.pbox(x0, x1, T - P['ua'], T - P['ua'] + 1, -2, 1, 'cuff')
    vest(c, 'vest')
    neckerchief(c, 'scarf')
    c.belt(L + 3)
    c.face('adult', mouth='MM')
    c.hair(side_bottom=7, back_bottom=3,
           bangs=[3, 3, 2, 3, 4, 3, 2, 2, 3, 2, 2, 3, 4, 3, 3, 3])
    hy, H = P['hy'], P['H']
    # tuft on top
    for (x, z) in ((-2, 1), (-1, 1), (-1, 2), (0, 0), (1, 1)):
        m.put(x, hy + H + 2, z, 'hair', 'Head')
    m.put(-1, hy + H + 3, 1, 'hair', 'Head')
    return c


def villager_man_a():
    c = Char('villager_man_a', 'man', {
        'shirt': '#ded0a8', 'skin': '#e8b491', 'pants': '#7a6a4c', 'shoe': '#4b3624',
        'hair': '#6b4526', 'beard': '#5a3a20', 'mouth': '#8a5344', 'vest': '#a76c3c',
        'belt': '#5e4028', 'metal': '#d3ad57', 'scarf': '#b45f36', 'iris': '#4a3322',
    })
    m, P = c.m, c.P
    L, T, hy, tw = P['L'], P['T'], P['hy'], P['tw']
    # belly
    m.box(-4, 4, L + 2, L + 8, 3, 4, 'shirt', 'Spine')
    for y in (L + 2,):
        m.put(-4, y, 3, 'shirt', 'Hips')
    for y in range(L + 2, L + 8):
        b = 'Hips' if y < L + 3 else 'Spine'
        for x in range(-4, 4):
            m.put(x, y, 3, 'shirt', b)
    for x in (-4, 3):
        m.rm(x, L + 2, 3)
        m.rm(x, L + 7, 3)
    vest(c, 'vest', front_z=3, belly=True)
    # scarf wrapped at the neck with a hanging end
    neckerchief(c, 'scarf')
    for y in range(T - 8, T - 2):
        m.put(-3, y, 4, 'scarf', c.tb(y))
        m.put(-2, y, 4, 'scarf', c.tb(y))
    c.belt(L + 2)
    c.face('adult', mouth='MM')
    c.hair(side_bottom=6, back_bottom=3,
           bangs=[2, 2, 2, 1, 1, 2, 1, 1, 1, 1, 2, 1, 1, 2, 2, 2])
    # beard & moustache
    my = c.mouth_y
    for x in range(-7, 7):
        for y in range(hy, my + 1):
            m.paint(x, y, 5, 'beard')
    for x in range(-3, 3):
        m.paint(x, my + 1, 5, 'beard')
    m.paint(-1, my, 5, 'mouth', 0)
    m.paint(0, my, 5, 'mouth', 0)
    for s in (-7, 6):
        for z in range(0, 6):
            for y in range(hy, hy + 5):
                m.paint(s, y, z, 'beard')
    m.box(-5, 5, hy, hy + 2, 6, 7, 'beard', 'Head')
    m.box(-4, 4, hy - 1, hy, 2, 7, 'beard', 'Head')
    m.box(-2, 2, hy - 2, hy - 1, 4, 7, 'beard', 'Head')
    return c


def villager_man_b():
    c = Char('villager_man_b', 'man', {
        'shirt': '#8b9bab', 'skin': '#d9a077', 'pants': '#4f4a44', 'shoe': '#3b2c1f',
        'hair': '#51402f', 'mouth': '#7d4a3d', 'apron': '#6d4a2e', 'apron_dk': '#5a3c24',
        'belt': '#4a3320', 'metal': '#cbb267', 'scarf': '#9c3f34', 'cap': '#4a4642',
        'cap_dk': '#3a3633', 'iris': '#3b2c20', 'sleeve_l': 'skin', 'stubble': '#b98763',
    })
    m, P = c.m, c.P
    L, T, hy, H, tw, K = P['L'], P['T'], P['hy'], P['H'], P['tw'], P['knee']
    # short sleeves: lower half of upper arm is skin
    for s in SIDES:
        x0, x1 = xr(s, tw, tw + 3)
        m.pbox(x0, x1, T - P['ua'], T - 3, -2, 1, 'skin', 0)
        m.pbox(x0, x1, T - 4, T - 3, -2, 1, 'shirt')
    neckerchief(c, 'scarf')
    # leather apron: bib + skirt in front of the legs
    for y in range(L + 3, T - 2):
        for x in range(-4, 4):
            m.put(x, y, 3, 'apron', c.tb(y))
    for y in range(L - 1, L + 3):
        for x in range(-4, 4):
            m.put(x, y, 3, 'apron', 'Hips')
    for y in range(K + 2, L - 1):
        for x in range(-4, 4):
            m.put(x, y, 4, 'apron', 'Hips')
    for x in range(-4, 4):
        m.put(x, L - 1, 4, 'apron', 'Hips')
    # pocket + stitch
    m.pbox(-2, 2, L - 5, L - 2, 4, 5, 'apron_dk')
    for s in SIDES:
        x0, x1 = xr(s, 2, 4)
        for y in range(T - 2, T + 0):
            for x in range(x0, x1):
                m.put(x, y, 3, 'apron', 'Chest')
        m.pbox(x0, x1, T - 1, T, -3, 3, 'apron')
        m.pbox(x0, x1, T - 12, T, -3, -2, 'apron')
    c.belt(L + 3)
    c.face('adult', mouth='MM')
    c.hair(side_bottom=6, back_bottom=3, bangs=[1] * 16)
    # stubble
    my = c.mouth_y
    for x in range(-6, 6):
        m.paint(x, hy, 5, 'stubble')
    for x in range(-3, 3):
        m.paint(x, my + 1, 5, 'stubble')
    m.paint(-1, my, 5, 'mouth', 0)
    m.paint(0, my, 5, 'mouth', 0)
    # flat cap over the hair
    top = hy + H
    for (x, y, z), (col, b, j) in list(m.v.items()):
        if b == 'Head' and col == 'hair' and y >= hy + 11:
            m.paint(x, y, z, 'cap')
    for x in range(-8, 8):
        for z in range(-7, 7):
            m.put(x, top + 1, z, 'cap', 'Head')
    for x in range(-7, 7):
        m.put(x, hy + 11, 7, 'cap_dk', 'Head')
        m.put(x, hy + 11, 8, 'cap_dk', 'Head')
        m.put(x, hy + 12, 7, 'cap', 'Head')
    for x in range(-8, 8):
        m.put(x, hy + 11, 6, 'cap_dk', 'Head')
    m.put(-1, top + 2, 0, 'cap_dk', 'Head')
    m.put(0, top + 2, 0, 'cap_dk', 'Head')
    return c


def villager_child_a():
    c = Char('villager_child_a', 'kid', {
        'shirt': '#ddab3e', 'shirt_dk': '#c4912c', 'skin': '#f0bd93', 'pants': '#8a6244',
        'shoe': '#5b422c', 'hair': '#b47b34', 'mouth': '#b06a55', 'belt': '#8d6b3c',
        'metal': '#aa8e4b', 'iris': '#4a7a3a', 'iris_lt': '#7fb05a', 'freckle': '#d0906a',
        'sleeve_l': 'skin', 'shin': 'skin', 'sock': '#efe6d4', 'brow': '#9a6428',
    })
    m, P = c.m, c.P
    L, T, hy, H, tw, K = P['L'], P['T'], P['hy'], P['H'], P['tw'], P['knee']
    for s in SIDES:
        x0, x1 = xr(s, tw, tw + 3)
        m.pbox(x0, x1, T - P['ua'], T - 3, -2, 1, 'skin', 0)
        x0, x1 = xr(s, 1, 5)
        m.pbox(x0, x1, K, K + 2, -2, 2, 'skin', 0)
        m.pbox(x0, x1, 4, 5, -2, 2, 'sock')
    # tunic hem over the hips and a collar
    for y in (L, L + 1, L + 2):
        m.pbox(-tw, tw, y, y + 1, -3, 3, 'shirt')
    m.pbox(-tw, tw, L, L + 1, -3, 3, 'shirt_dk')
    m.pbox(-2, 2, T - 1, T, 2, 3, 'skin', 0)
    m.paint(-1, T - 2, 2, 'skin', 0)
    m.paint(0, T - 2, 2, 'skin', 0)
    c.belt(L + 3)
    c.face('small', mouth='')
    for x in (-6, -4, 3, 5):
        m.paint(x, c.mouth_y + 1, 5, 'freckle', 0)
    c.hair(side_bottom=6, back_bottom=2,
           bangs=[3, 3, 4, 3, 2, 3, 4, 2, 3, 4, 3, 2, 3, 4, 3, 3])
    # spiky top
    for (x, z) in ((-5, 0), (-3, 2), (-1, -2), (1, 1), (3, -1), (4, 3), (-2, -4), (2, -5)):
        m.put(x, hy + H + 2, z, 'hair', 'Head')
        m.put(x + 1, hy + H + 2, z, 'hair', 'Head')
    m.put(-1, hy + H + 3, -2, 'hair', 'Head')
    m.put(1, hy + H + 3, 1, 'hair', 'Head')
    return c


def villager_child_b():
    c = Char('villager_child_b', 'kid', {
        'shirt': '#e59fa2', 'skin': '#f6c8a8', 'pants': '#d1848c', 'shoe': '#6b4a30',
        'hair': '#5e3a24', 'mouth': '#c07264', 'apron': '#f3e6cf', 'belt': '#b0705f',
        'metal': '#aa8e4b', 'iris': '#5a3a26', 'ribbon': '#d9606e',
        'sleeve_l': 'skin', 'thigh': 'skin', 'shin': 'skin', 'sock': '#fff8ee',
    })
    m, P = c.m, c.P
    L, T, hy, H, tw, K = P['L'], P['T'], P['hy'], P['H'], P['tw'], P['knee']
    for s in SIDES:
        x0, x1 = xr(s, tw, tw + 3)
        m.pbox(x0, x1, T - P['ua'], T - 2, -2, 1, 'skin', 0)
        # puffy sleeve
        x0, x1 = xr(s, tw + 3, tw + 4)
        m.box(x0, x1, T - 3, T, -2, 1, 'shirt', s + 'UpperArm')
        x0, x1 = xr(s, 1, 5)
        m.pbox(x0, x1, 3, 6, -2, 2, 'sock')
    m.pbox(-tw, tw, L, L + 3, -3, 3, 'pants')
    c.skirt(L + 3, K - 1, 6, 8, 4, 6, 'pants', hem='apron')
    # apron front on the skirt and a bib
    for (x, y, z), (col, b, j) in list(m.v.items()):
        if b == 'Hips' and -3 <= x < 3 and z >= 3 and y < L + 3 and y >= K:
            m.paint(x, y, z, 'apron')
    for y in range(L + 3, T - 2):
        for x in range(-3, 3):
            m.put(x, y, 3, 'apron', c.tb(y))
    m.pbox(-2, 2, T - 1, T, 2, 3, 'apron')
    c.belt(L + 3, 'ribbon', 'ribbon')
    m.put(-2, L + 3, 3, 'ribbon', 'Spine', 0)
    m.put(1, L + 3, 3, 'ribbon', 'Spine', 0)
    c.face('small', mouth='')
    c.hair(side_bottom=3, back_bottom=0,
           bangs=[5, 4, 3, 3, 4, 3, 3, 2, 2, 3, 3, 4, 3, 3, 4, 5])
    # pigtails
    for s in SIDES:
        g = 1 if s == 'L' else -1
        x0, x1 = xr(s, 8, 11)
        rx0, rx1 = xr(s, 8, 10)
        segs = [
            [(rx0, rx1, hy + 8, hy + 10, -4, -1, 'ribbon'),
             (x0, x1, hy + 5, hy + 8, -4, -1, 'hair')],
            [(x0, x1, hy + 1, hy + 5, -4, -1, 'hair'),
             (xr(s, 9, 10)[0], xr(s, 9, 10)[1], hy - 1, hy + 1, -3, -2, 'hair')],
        ]
        piv = [(g * 9.5, hy + 9, -2.5), (g * 9.5, hy + 5, -2.5)]
        names = c.tail_chain(s + 'Tail', 'Head', piv, segs)
        c.tails += [(names[0], 1.0), (names[1], 0.6)]
        # ribbon bows
        bx0, bx1 = xr(s, 10, 12)
        m.box(bx0, bx1, hy + 9, hy + 11, -3, -2, 'ribbon', names[0])
    return c


def villager_woman_a():
    c = Char('villager_woman_a', 'woman', {
        'shirt': '#b1544a', 'skin': '#eebb9a', 'pants': '#a4463c', 'shoe': '#5a3f2b',
        'hair': '#77492a', 'mouth': '#b4675c', 'apron': '#f1e7cd', 'belt': '#8a5a3a',
        'metal': '#aa8e4b', 'iris': '#4b6a3a', 'iris_lt': '#7a9a5a', 'collar': '#f1e7cd',
    })
    m, P = c.m, c.P
    L, T, hy, H, tw = P['L'], P['T'], P['hy'], P['H'], P['tw']
    m.pbox(-tw, tw, L, L + 3, -3, 3, 'pants')
    c.skirt(L + 3, 3, 6, 8, 4, 6, 'pants')
    for (x, y, z), (col, b, j) in list(m.v.items()):
        if b == 'Hips' and -4 <= x < 4 and z >= 3 and 5 <= y < L + 3:
            m.paint(x, y, z, 'apron')
    for y in range(L + 3, L + 8):
        for x in range(-3, 3):
            m.put(x, y, 3, 'apron', c.tb(y))
    m.pbox(-3, 3, T - 1, T, -3, 3, 'collar')
    m.pbox(-tw, tw, T - 1, T, 2, 3, 'collar')
    c.belt(L + 3)
    c.face('small', mouth='')
    c.hair(side_bottom=2, back_bottom=-1,
           bangs=[6, 5, 3, 2, 2, 3, 2, 2, 2, 2, 3, 2, 2, 3, 5, 6])
    # bun
    m.box(-2, 2, hy + 8, hy + 13, -9, -7, 'hair', 'Head')
    m.box(-3, 3, hy + 9, hy + 12, -9, -7, 'hair', 'Head')
    m.box(-1, 1, hy + 9, hy + 12, -10, -9, 'hair', 'Head')
    m.box(-3, 3, hy + 7, hy + 8, -8, -7, 'apron', 'Head')
    return c


def villager_woman_b():
    c = Char('villager_woman_b', 'woman', {
        'shirt': '#f2ead2', 'skin': '#f0c1a2', 'pants': '#7e8a4e', 'shoe': '#574029',
        'hair': '#4a3524', 'mouth': '#b8695e', 'scarf': '#48678a', 'trim': '#e0d2ad',
        'bodice': '#3f5a74', 'belt': '#6a5238', 'metal': '#aa8e4b', 'iris': '#3d5a7a',
        'iris_lt': '#6a8ab0',
    })
    m, P = c.m, c.P
    L, T, hy, H, tw = P['L'], P['T'], P['hy'], P['H'], P['tw']
    # puffy sleeves
    for s in SIDES:
        x0, x1 = xr(s, tw + 3, tw + 4)
        m.box(x0, x1, T - 4, T, -2, 1, 'shirt', s + 'UpperArm')
    m.pbox(-tw, tw, L, L + 3, -3, 3, 'pants')
    c.skirt(L + 3, 3, 6, 8, 4, 6, 'pants', hem='trim', hem_rows=2)
    # bodice with lacing
    for y in range(L + 3, T - 3):
        m.pbox(-tw, tw, y, y + 1, -3, 3, 'bodice')
        for x in range(-3, 3):
            m.put(x, y, 3, 'bodice', c.tb(y))
    for y in range(L + 4, T - 3, 2):
        m.paint(-1, y, 3, 'trim', 0)
        m.paint(0, y, 3, 'trim', 0)
    c.belt(L + 3, 'belt')
    c.face('small', mouth='')
    c.hair(side_bottom=3, back_bottom=0,
           bangs=[4, 3, 2, 2, 3, 2, 2, 3, 3, 2, 2, 3, 2, 2, 3, 4])
    # headscarf over the top of the head
    top = hy + H
    for (x, y, z), (col, b, j) in list(m.v.items()):
        if b == 'Head' and col == 'hair' and y >= hy + 11:
            m.paint(x, y, z, 'scarf')
    for x in range(-8, 8):
        m.put(x, hy + 11, 7, 'trim', 'Head')
        m.put(x, hy + 12, 7, 'scarf', 'Head')
        m.put(x, top, 7, 'scarf', 'Head')
        m.put(x, top - 1, 7, 'scarf', 'Head')
    for z in range(-7, 7):
        m.put(-9, hy + 11, z, 'trim', 'Head')
        m.put(8, hy + 11, z, 'trim', 'Head')
    # knot at the back
    m.box(-2, 2, hy + 9, hy + 12, -9, -8, 'scarf', 'Head')
    m.box(-2, 1, hy + 6, hy + 9, -9, -8, 'scarf', 'Head')
    # braid down the back
    segs = [
        [(-1, 1, hy - 4, hy + 3, -8, -6, 'hair')],
        [(-1, 1, hy - 9, hy - 4, -7, -5, 'hair'),
         (-1, 1, hy - 10, hy - 9, -7, -5, 'trim')],
    ]
    names = c.tail_chain('Braid', 'Head', [(0, hy + 2, -7), (0, hy - 4, -6)], segs)
    c.tails += [(names[0], 1.0), (names[1], 0.6)]
    for y in range(hy - 4, hy + 3, 2):
        m.paint(-1, y, -8, 'hair', 0)
    return c


def vest(c, color, front_z=2, belly=False):
    m, P = c.m, c.P
    L, T, tw = P['L'], P['T'], P['tw']
    for (x, y, z), (col, b, j) in list(m.v.items()):
        if b in ('Spine', 'Chest') and y < T - 1:
            front = z >= 2
            if front and -2 <= x < 2:
                continue
            m.paint(x, y, z, color)
    for y in range(L + 3, T - 1):
        for x in list(range(-tw, -2)) + list(range(2, tw)):
            if m.get(x, y, front_z + 1) is None:
                m.put(x, y, front_z + 1, color, c.tb(y))
    m.pbox(-tw, tw, T - 1, T, -3, 3, color)
    m.pbox(-2, 2, T - 1, T, 2, 3, 'shirt')


def neckerchief(c, color):
    m, P = c.m, c.P
    T = P['T']
    m.pbox(-2, 2, T, T + 1, -2, 2, color)
    for d, (a, b) in enumerate(((-3, 3), (-2, 2), (-1, 1))):
        for x in range(a, b):
            m.put(x, T - 1 - d, 3, color, 'Chest')


# ---------------------------------------------------------------- animations
TAU = 2 * math.pi


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def env(t, dur, a, b):
    """0 -> 1 over [0,a], hold, 1 -> 0 over [dur-b, dur]."""
    return smooth(t / a) * smooth((dur - t) / b)


class Pose:
    def __init__(self):
        self.r = {}
        self.off = [0.0, 0.0, 0.0]

    def add(self, bone, x=0.0, y=0.0, z=0.0):
        a = self.r.get(bone, (0.0, 0.0, 0.0))
        self.r[bone] = (a[0] + x, a[1] + y, a[2] + z)

    def sym(self, part, x=0.0, y=0.0, z=0.0):
        """z mirrored so that positive z = outward on both sides."""
        self.add('L' + part, x, y, z)
        self.add('R' + part, x, -y, -z)

    def pitch(self):
        return sum(self.r.get(b, (0, 0, 0))[0] for b in ('Spine', 'Chest', 'Neck', 'Head'))


def make_clips(c):
    kid = c.kind == 'kid'
    sk = c.has_skirt
    P = c.P

    def finish(p, t, sway):
        # arms relax outward a little, tails hang and sway
        pitch = p.pitch()
        for bn, gain in c.tails:
            p.add(bn, x=-pitch * 0.8 * gain + sway[0] * gain, z=sway[1] * gain)
        return p.r, tuple(p.off)

    def breathe(p, t, per=4.0, amt=1.0):
        ph = TAU * t / per
        p.add('Chest', x=0.025 * amt * math.sin(ph))
        p.add('Head', x=-0.02 * amt * math.sin(ph))
        p.sym('UpperArm', z=0.07 + 0.02 * amt * math.sin(ph))
        p.sym('LowerArm', x=-0.12)
        p.off[1] += 0.002 * amt * math.sin(ph)

    def idle(t):
        p = Pose()
        breathe(p, t)
        ph = TAU * t / 4.0
        p.add('Head', y=0.08 * math.sin(ph), z=0.03 * math.sin(2 * ph))
        p.add('Hips', z=0.015 * math.sin(ph))
        p.add('Spine', z=-0.015 * math.sin(ph))
        return finish(p, t, (0.04 * math.sin(ph + 1), 0.05 * math.sin(ph)))

    def walk_fn(dur, run=False):
        def f(t):
            p = Pose()
            ph = TAU * t / dur
            s = math.sin(ph)
            co = math.cos(ph)
            if run:
                A = 0.6 if sk else 0.8
                B, C = 1.3, 0.85
            else:
                A = 0.36 if sk else (0.55 if kid else 0.48)
                B, C = 0.65, 0.45 if kid else 0.38
            for side, g in (('L', 1), ('R', -1)):
                th = -A * s * g
                kn = B * max(0.0, co * g) + (0.35 if run else 0.05)
                p.add(side + 'Thigh', x=th)
                p.add(side + 'Shin', x=kn)
                p.add(side + 'Foot', x=-(th + kn) * 0.5 + (0.1 if run else 0))
                p.add(side + 'UpperArm', x=C * s * g)
            if run:
                p.sym('LowerArm', x=-1.3)
                p.sym('UpperArm', z=0.12)
                p.add('Spine', x=0.22)
                p.add('Head', x=-0.12)
                p.off[1] += -0.012 + 0.03 * (0.5 + 0.5 * math.cos(2 * ph))
            else:
                p.sym('LowerArm', x=-0.3)
                p.sym('UpperArm', z=0.08)
                p.add('Spine', x=0.05)
                p.off[1] += 0.012 * (math.cos(2 * ph)) * (1.3 if kid else 1.0)
            p.add('Hips', y=0.1 * s)
            p.add('Chest', y=-0.14 * s)
            p.add('Hips', z=0.03 * s * (-1))
            p.add('Head', y=0.04 * s)
            amp = 0.25 if run else 0.12
            return finish(p, t, (amp * math.cos(2 * ph) + (0.3 if run else 0.08), amp * 0.6 * s))
        return f

    def wave(t):
        dur = 2.0
        p = Pose()
        breathe(p, t, 2.0, 0.5)
        e = env(t, dur, 0.35, 0.35)
        w = math.sin(TAU * 3 * t / dur)
        p.add('RUpperArm', x=-0.25 * e, z=-2.55 * e)
        p.add('RLowerArm', z=e * (-0.25 + 0.4 * w), x=-0.2 * e)
        p.add('RHand', z=0.2 * e * w)
        p.add('Head', z=0.12 * e, y=-0.1 * e)
        p.add('Chest', z=0.06 * e)
        return finish(p, t, (0, -0.1 * e + 0.05 * w * e))

    def nod(t):
        dur = 1.25
        p = Pose()
        breathe(p, t, 1.25, 0.3)
        e = env(t, dur, 0.1, 0.15)
        n = max(0.0, math.sin(TAU * 2 * t / dur))
        p.add('Head', x=0.35 * n * e)
        p.add('Neck', x=0.12 * n * e)
        return finish(p, t, (0.2 * n * e, 0))

    def shake(t):
        dur = 1.5
        p = Pose()
        breathe(p, t, 1.5, 0.3)
        e = env(t, dur, 0.15, 0.25)
        n = math.sin(TAU * 3 * t / dur)
        p.add('Head', y=0.4 * n * e, x=0.05 * e)
        p.add('Neck', y=0.1 * n * e)
        return finish(p, t, (0, -0.25 * n * e))

    def bow(t):
        dur = 2.0
        p = Pose()
        e = smooth(t / 0.55) * smooth((dur - t) / 0.6)
        p.add('Spine', x=0.45 * e)
        p.add('Chest', x=0.3 * e)
        p.add('Head', x=0.2 * e)
        p.sym('UpperArm', x=-0.6 * e, z=0.07 - 0.15 * e)
        p.sym('LowerArm', x=-0.12 - 0.35 * e)
        p.sym('Hand', z=-0.3 * e)
        p.add('LThigh', x=0.08 * e)
        p.add('RThigh', x=0.08 * e)
        p.add('LFoot', x=-0.08 * e)
        p.add('RFoot', x=-0.08 * e)
        p.off[2] -= 0.03 * e
        return finish(p, t, (0, 0))

    def talk(t):
        dur = 2.5
        p = Pose()
        breathe(p, t, 2.5, 0.6)
        ph = TAU * t / dur
        p.add('RUpperArm', x=-0.35 + 0.12 * math.sin(ph), z=-0.1)
        p.add('RLowerArm', x=-1.0 - 0.3 * math.sin(2 * ph))
        p.add('RHand', z=-0.2 + 0.25 * math.sin(2 * ph + 1), y=0.3)
        p.add('LUpperArm', x=-0.15 - 0.1 * math.sin(ph + 2))
        p.add('LLowerArm', x=-0.5 - 0.3 * max(0, math.sin(ph + 2)))
        p.add('Head', x=0.06 * math.sin(3 * ph), y=0.12 * math.sin(ph))
        p.add('Chest', y=0.06 * math.sin(ph))
        return finish(p, t, (0.05 * math.sin(3 * ph), 0.06 * math.sin(ph)))

    def joy(t):
        dur = 2.0
        p = Pose()
        e = env(t, dur, 0.25, 0.3)
        s = math.sin(TAU * 2 * t / dur - 0.6)
        air = max(0.0, s)
        crouch = max(0.0, -s)
        hop = (0.07 if kid else 0.05)
        p.off[1] += e * (hop * air - 0.03 * crouch)
        for side in SIDES:
            p.add(side + 'Thigh', x=-0.55 * crouch * e)
            p.add(side + 'Shin', x=1.1 * crouch * e)
            p.add(side + 'Foot', x=(-0.55 * crouch + 0.3 * air) * e)
        w = math.sin(TAU * 4 * t / dur)
        p.sym('UpperArm', z=e * (2.5 + 0.15 * w), x=-0.2 * e)
        p.sym('LowerArm', z=e * (0.25 + 0.15 * w))
        p.add('Head', x=-0.18 * e)
        p.add('Spine', x=-0.06 * e)
        return finish(p, t, (0.3 * crouch * e - 0.2 * air * e, 0))

    def surprise(t):
        dur = 1.5
        p = Pose()
        e = smooth(t / 0.12) * smooth((dur - t) / 0.5)
        p.add('Spine', x=-0.12 * e)
        p.add('Chest', x=-0.1 * e)
        p.add('Head', x=-0.18 * e)
        p.sym('UpperArm', x=-0.35 * e, z=0.55 * e)
        p.sym('LowerArm', x=-1.3 * e)
        p.sym('Hand', x=-0.3 * e)
        p.add('LThigh', x=0.12 * e)
        p.add('LShin', x=0.1 * e)
        p.off[1] += 0.015 * math.sin(math.pi * min(1.0, t / 0.3))
        p.off[2] -= 0.02 * e
        return finish(p, t, (-0.2 * e, 0))

    def sad(t):
        dur = 3.0
        p = Pose()
        ph = TAU * t / dur
        breathe(p, t, 3.0, 0.5)
        p.add('Head', x=0.45, y=0.08 * math.sin(ph))
        p.add('Neck', x=0.1)
        p.add('Chest', x=0.14)
        p.add('Spine', x=0.05)
        p.sym('UpperArm', x=0.05, z=-0.05)
        p.sym('LowerArm', x=-0.05)
        p.off[1] -= 0.006
        return finish(p, t, (0.03 * math.sin(ph), 0))

    def hurt(t):
        dur = 1.25
        p = Pose()
        e = (t / 0.1) if t < 0.1 else ((dur - t) / (dur - 0.1)) ** 2
        p.add('Spine', x=-0.3 * e)
        p.add('Chest', x=-0.2 * e)
        p.add('Head', x=-0.3 * e, z=0.1 * e)
        p.sym('UpperArm', x=-0.35 * e, z=0.4 * e)
        p.sym('LowerArm', x=-0.7 * e)
        for side in SIDES:
            p.add(side + 'Thigh', x=-0.2 * e)
            p.add(side + 'Shin', x=0.4 * e)
            p.add(side + 'Foot', x=-0.2 * e)
        p.off[1] -= 0.02 * e
        p.off[2] -= 0.03 * e
        return finish(p, t, (-0.4 * e, 0.1 * e))

    wd = 0.8 if kid else 1.0
    rd = 0.5 if kid else 0.6
    return [
        ('Idle', 4.0, idle),
        ('Walk', wd, walk_fn(wd)),
        ('Run', rd, walk_fn(rd, run=True)),
        ('Wave', 2.0, wave),
        ('Nod', 1.25, nod),
        ('ShakeHead', 1.5, shake),
        ('Bow', 2.0, bow),
        ('Talk', 2.5, talk),
        ('Joy', 2.0, joy),
        ('Surprise', 1.5, surprise),
        ('Sad', 3.0, sad),
        ('Hurt', 1.25, hurt),
    ]


CHARACTERS = [villager, villager_man_a, villager_man_b, villager_child_a,
              villager_child_b, villager_woman_a, villager_woman_b]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'villagers')
    os.makedirs(out, exist_ok=True)
    only = sys.argv[2:] or None
    for fn in CHARACTERS:
        if only and fn.__name__ not in only:
            continue
        c = fn()
        info = write_glb(os.path.join(out, c.name + '.glb'), c.name, c.m, c.pal, c.bones(), make_clips(c))
        print(c.name, info)


if __name__ == '__main__':
    main()
