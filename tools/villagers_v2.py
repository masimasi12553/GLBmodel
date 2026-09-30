#!/usr/bin/env python3
"""Generate the v2 voxel villagers (7 characters, soft-skinned rig, 19 animations, blinking).

usage: python3 tools/villagers_v2.py [out_dir] [character ...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anim2 import build_clips  # noqa: E402
from charkit import SIDES, Char  # noqa: E402
from vox2 import mir, xr  # noqa: E402


def dims(c):
    d = c.d
    return d['L'], d['K'], d['T'], d['hy'], d['ytop'], d['tw'], d['ua'], d['la']


def _rnd(x, y, z):
    """Deterministic pseudo random number in [0, 1) for a voxel."""
    h = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xffff) / 65536.0


def scarf_ring(c, colour, hang=True):
    """Neckerchief: wraps the neck row and hangs as a small triangle on the chest."""
    L, K, T, hy, ytop, tw, ua, la = dims(c)
    c.paint_where(lambda x, y, z, b, col: b == 'Neck', colour)
    c.rect(-3, 3, T - 1, T, 2, colour)
    c.rect(-3, 3, T - 1, T, -3, colour)
    if hang:
        c.rect(-2, 2, T - 2, T - 1, 2, colour)
        c.rect(-1, 1, T - 3, T - 2, 2, colour)
        for x in (-1, 0):
            c.ov(x, T - 2, 3, c.t(colour, 0.82))


# ====================================================================== 1. villager
def villager():
    pal = dict(skin='#e8b89a', hair='#6b4a2e', iris='#4a3222', mouth='#a4604f',
               shirt='#e2d5b4', vest='#8f5c39', scarf='#a8562f', pants='#7d6a51', shoe='#4b3827',
               belt='#5d4130', metal='#aa8e4b', cuff='#f0e8cf', lace='#b7a883', leather='#7a4f2e',
               patch='#93806a')
    c = Char('villager', 'man', pal)
    m = c.m
    L, K, T, hy, ytop, tw, ua, la = dims(c)

    c.legs('pants', 'shoe', boot_top=6)
    c.rect(-4, -2, K - 1, K + 2, 1, 'patch')                    # patched right knee
    c.torso_paint('shirt')
    c.arms_paint(upper='shirt')
    for s in SIDES:                                              # rolled-up sleeves
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'UpperArm' and T - ua <= y < T - ua + 2, 'cuff')
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'UpperArm' and y == T - ua + 2, c.t('shirt', 0.88))

    def opening(y):
        return (-3, 2) if y >= T - 1 else (-2, 1)

    def is_vest(x, y, z, b, col):
        if b not in ('Spine', 'Chest') or y < L + 3:
            return False
        if z >= 0 and opening(y)[0] <= x <= opening(y)[1]:
            return False
        return True
    c.paint_where(is_vest, 'vest')
    for y in range(L + 3, T - 3):                                # thick front panels
        for x in (-5, -4, -3, 2, 3, 4):
            f = 0.86 if x in (-3, 2) else 1.0
            if y == L + 3:
                f *= 0.9
            c.ov(x, y, 3, c.t('vest', f))
    for x in (2, 3, 4):
        m.paint(x, L + 5, 3, c.t('vest', 0.8))                   # pocket welt
    for x in range(-5, 5):
        m.paint(x, T - 6, -3, c.t('vest', 0.88))                 # back yoke seam
    for x in range(-4, 4):
        c.ov(x, L + 6, -4, 'leather')                            # cinch strap
    c.ov(-1, L + 6, -4, 'metal', 0)
    c.ov(0, L + 6, -4, 'metal', 0)
    scarf_ring(c, 'scarf')
    for (x, y) in ((-1, T - 4), (0, T - 5), (-1, T - 6), (0, T - 7)):
        m.paint(x, y, 2, 'lace', 0)                              # lace-up placket

    c.belt(L + 2)
    for x in (2, 3, 4):                                          # belt pouch
        for y in (L, L + 1):
            for z in (3, 4):
                m.put(x, y, z, c.t('leather', 0.95 if y == L else 0.8), 'Hips', 1.0)
    m.put(3, L + 1, 5, 'metal', 'Hips', 0)

    c.face(brow=('hair', 3, 2), nose=2, mouth=2)
    c.ears()
    c.hair('hair', side_bottom=7, back_bottom=3, sideburn=5,
           bangs=[1, 2, 3, 3, 4, 4, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1],
           tufts=[(-3, 3, 1), (-2, 3, 1), (-2, 3, 2), (-3, 3, 0), (-1, 3, 0)])
    return c


# ====================================================================== 2. villager_man_a
def villager_man_a():
    pal = dict(skin='#e8b491', hair='#6b4526', beard='#5a3a20', grey='#8b7a66', iris='#3f2c1d', mouth='#5a2a22',
               shirt='#ded0a8', vest='#a76c3c', scarf='#b45f36', pants='#7a6a4c', shoe='#4b3624',
               belt='#5e4028', metal='#d3ad57', cuff='#efe3bd', patch='#b69c6a', leather='#6f4a2c')
    c = Char('villager_man_a', 'man', pal)
    m = c.m
    L, K, T, hy, ytop, tw, ua, la = dims(c)

    c.legs('pants', 'shoe', boot_top=6)
    c.torso_paint('shirt')
    c.arms_paint(upper='shirt', lower='shirt', cuff=('cuff', 1))
    for x in (-8, -7):                                           # elbow patch
        for y in (T - ua - 1, T - ua):
            m.paint(x, y, -2, 'patch')

    def opening(y):
        if y >= T - 2:
            return (-3, 2)
        if y >= T - 4:
            return (-2, 1)
        if y >= T - 6:
            return (-1, 0)
        return None

    def is_vest(x, y, z, b, col):
        if b not in ('Spine', 'Chest') or y < L + 3:
            return False
        o = opening(y)
        return not (z >= 0 and o and o[0] <= x <= o[1])
    c.paint_where(is_vest, 'vest')
    belly = {L + 1: (-3, 2), L + 2: (-4, 3), L + 3: (-4, 3), L + 4: (-4, 3), L + 5: (-4, 3),
             L + 6: (-4, 3), L + 7: (-3, 2), L + 8: (-2, 1)}
    for y, (x0, x1) in belly.items():
        for x in range(x0, x1 + 1):
            c.ov(x, y, 3, 'belt' if y == L + 2 else c.t('vest', 0.9 if y == L + 1 else 1.0))
    for y in list(range(L + 3, T - 6)):
        m.paint(-1, y, 2, c.t('vest', 0.86))
        if (-1, y, 3) in m.v:
            m.paint(-1, y, 3, c.t('vest', 0.86))
    for y in range(L + 3, L + 8):                                # second layer: a proper belly
        for x in range(-3, 3):
            if not (y in (L + 3, L + 7) and x in (-3, 2)):
                c.ov(x, y, 4, c.t('vest', 0.97))
    for y in (L + 3, L + 5, L + 7):
        c.ov(0, y, 5, 'metal', 0)                                # brass buttons
    c.ov(0, L + 10, 3, 'metal', 0)
    scarf_ring(c, 'scarf', hang=False)
    for y in range(T - 9, T - 1):                                # scarf end hanging on the chest
        f = 0.8 if (T - y) % 3 == 0 else 1.0
        for x in (-4, -3):
            c.ov(x, y, 3, c.t('scarf', f))
    c.belt(L + 2)
    for x in range(-4, 4):
        if (x, L + 2, 3) not in m.v:
            c.ov(x, L + 2, 3, 'belt')
    for x in range(-4, 4):
        c.ov(x, L + 6, -4, 'leather')
    for x in (3, 4, 5):                                          # flask on the hip
        m.put(x, L - 1, -3, 'leather', 'Hips', 1.0)
        m.put(x, L, -3, 'leather', 'Hips', 1.0)

    c.face(brow=('hair', 3, 2), nose=2, mouth=None)
    c.ears()
    c.hair('hair', side_bottom=6, back_bottom=2,
           bangs=[0, 0, 0, 1, 1, 2, 2, 2, 2, 2, 2, 1, 1, 0, 0, 0])
    for (x, y, z), (col, b, j) in list(m.v.items()):             # a little grey at the temples
        if b == 'Head' and x in (-8, 7) and hy + 8 <= y <= ytop - 2 and z >= 1 and _rnd(x, y, z) < 0.25:
            m.v[(x, y, z)] = (c.mix('hair', 'grey', 0.55), b, 1.0)

    def bcol(x, y, z):
        if _rnd(x, y, z) < 0.09:
            return c.t('grey', 0.95)
        return c.t('beard', (0.92, 1.0, 1.06, 0.96)[(x + y) % 4])
    for x in range(-7, 7):
        for y in range(hy, hy + 3):
            m.paint(x, y, 5, bcol(x, y, 5), 1.0)
    for x in list(range(-7, -4)) + list(range(4, 7)):
        for y in range(hy + 3, hy + 6):
            m.paint(x, y, 5, bcol(x, y, 5), 1.0)
    for y in range(hy, hy + 6):
        for z in range(0, 5):
            for x in (-7, 6):
                m.paint(x, y, z, bcol(x, y, z), 1.0)
    for y in range(hy, hy + 3):
        for x in range(-6, 6):
            m.put(x, y, 6, bcol(x, y, 6), 'Head', 1.0)
    for y in range(hy, hy + 2):
        for x in range(-4, 4):
            m.put(x, y, 7, bcol(x, y, 7), 'Head', 1.0)
    for x in range(-4, 4):                                       # moustache
        m.paint(x, hy + 3, 5, bcol(x, hy + 3, 5), 1.0)
        m.put(x, hy + 3, 6, bcol(x, hy + 3, 6), 'Head', 1.0)
    for x in (-1, 0):
        m.put(x, hy + 2, 6, 'mouth', 'Head', 0)
    return c


# ====================================================================== 3. villager_man_b
def villager_man_b():
    pal = dict(skin='#d9a077', hair='#51402f', iris='#2f241b', mouth='#7d4a3d', shirt='#8b9bab',
               apron='#6d4a2e', apron_dk='#57391f', scarf='#9c3f34', pants='#4f4a44', shoe='#3b2c1f',
               belt='#4a3320', metal='#cbb267', steel='#8f939b', cap='#4a4642', wood='#8a6238',
               band='#4a3320', stubble='#bf8a62')
    c = Char('villager_man_b', 'man', pal)
    m = c.m
    L, K, T, hy, ytop, tw, ua, la = dims(c)

    c.legs('pants', 'shoe', boot_top=7)
    c.paint_where(lambda x, y, z, b, col: b.endswith('Foot') and y == 1 and z in (1, 2), 'steel')
    c.torso_paint('shirt')
    c.arms_paint(upper='shirt', upper_rows=(0, 4), cuff=('band', 1))
    for s in SIDES:
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'UpperArm' and y == T - 4, c.t('shirt', 0.86))

    ap, apd = 'apron', 'apron_dk'
    for y in range(L + 3, T - 2):                                # bib
        for x in (range(-3, 3) if y < T - 4 else range(-2, 2)):
            c.ov(x, y, 3, ap)
    for y in (T - 2, T - 1):                                     # straps over the shoulders
        for x in (-3, -2, 1, 2):
            m.paint(x, y, 2, apd)
    for x in (-3, -2, 1, 2):
        for z in range(-3, 3):
            m.paint(x, T - 1, z, apd)
    cross = {T - 2: ((-3, -2), (1, 2)), T - 3: ((-2, -1), (0, 1)), T - 4: ((-1, 0), (-1, 0)),
             T - 5: ((0, 1), (-2, -1)), T - 6: ((1, 2), (-3, -2))}
    for y, (a, b) in cross.items():                              # crossed straps on the back
        for x in a + b:
            m.paint(x, y, -3, apd)
    for y in range(L + 3, T - 6):
        for x in (-3, -2, 1, 2):
            m.paint(x, y, -3, apd)
    c.rect(-4, 4, L, L + 2, 2, ap)
    for y in range(K + 2, L):                                    # apron skirt follows each thigh
        for x in range(-4, 4):
            bone = 'LThigh' if x >= 1 else ('RThigh' if x <= -2 else 'Hips')
            m.put(x, y, 2, c.t(ap, 0.85 if y == K + 2 else 1.0), bone, 1.0)
    for y in range(K + 4, K + 7):                                # pockets
        for x in (-4, -3, -2):
            m.put(x, y, 3, apd, 'RThigh', 1.0)
        for x in (1, 2, 3):
            m.put(x, y, 3, apd, 'LThigh', 1.0)
    for y in (K + 7, K + 8, K + 9):                              # tongs and a chisel poking out
        m.put(-3, y, 3, 'steel', 'RThigh', 0)
    for y in (K + 7, K + 8):
        m.put(-2, y, 3, 'steel', 'RThigh', 0)
    m.put(-4, K + 7, 3, 'wood', 'RThigh', 1.0)
    m.put(-4, K + 8, 3, 'wood', 'RThigh', 1.0)
    m.put(-4, K + 9, 3, 'steel', 'RThigh', 0)
    c.ov(-2, T - 3, 3, 'metal', 0)                               # rivets
    c.ov(1, T - 3, 3, 'metal', 0)

    c.belt(L + 2)
    for x in range(-4, 4):
        if (x, L + 2, 3) not in m.v:
            c.ov(x, L + 2, 3, 'belt')
    for y in range(L - 3, L + 2):                                # hammer hanging at the back
        m.put(-4, y, -4, 'wood', 'Hips', 1.0)
    for x in range(-6, -2):
        for y in (L + 2, L + 3):
            for z in (-5, -4):
                m.put(x, y, z, c.t('steel', 1.0 if x < -3 else 0.85), c.tb(y), 0.5)
    scarf_ring(c, 'scarf')

    c.face(brow=('hair', 3, 2), nose=2, mouth=2)
    c.ears()
    c.hair('hair', side_bottom=8, back_bottom=5, top_layers=1, crown_rows=2, sideburn=6, bangs=[0] * 16)
    for x in range(-7, 7):                                       # stubble
        for y in range(hy, hy + 4):
            if _rnd(x, y, 5) < 0.55:
                m.paint(x, y, 5, 'stubble', 0.6)
    for x in (-1, 0):
        m.paint(x, hy + 2, 5, 'mouth', 0)
    # flat cap
    cap, cap_dk, cap_lt = 'cap', c.t('cap', 0.8), c.t('cap', 1.14)
    for x in range(-8, 8):
        for z in range(-7, 7):
            if (x in (-8, 7)) and (z in (-7, 6)):
                continue
            m.put(x, ytop + 1, z, cap_lt if (x + z) % 5 else cap, 'Head', 1.0)
    for x in range(-7, 7):
        for z in range(-6, 6):
            if (x in (-7, 6)) and (z in (-6, 5)):
                continue
            m.put(x, ytop + 2, z, cap, 'Head', 1.0)
    for y in (ytop - 1, ytop):
        for x in range(-8, 8):
            for z in (-7, 6):
                m.put(x, y, z, cap_dk if y == ytop - 1 else cap, 'Head', 1.0)
        for z in range(-7, 7):
            for x in (-8, 7):
                m.put(x, y, z, cap_dk if y == ytop - 1 else cap, 'Head', 1.0)
    for x in range(-6, 6):                                       # visor
        m.put(x, ytop, 7, cap_dk, 'Head', 1.0)
        m.put(x, ytop - 1, 7, cap_dk, 'Head', 1.0)
        m.put(x, ytop - 1, 8, cap_dk, 'Head', 1.0)
    m.put(-1, ytop + 3, 0, cap_dk, 'Head', 1.0)
    return c


# ====================================================================== 4. villager_child_a
def villager_child_a():
    pal = dict(skin='#f0bd93', hair='#b47b34', iris='#4d6a35', mouth='#b06a55', shirt='#ddab3e',
               shirt_dk='#c4912c', pants='#8a6244', shoe='#5b422c', belt='#8d6b3c', metal='#aa8e4b',
               sock='#efe6d4', lace='#c9a04a', patch='#a9784f', wood='#8a6238', plaster='#f3ead8',
               freckle='#dea77f')
    c = Char('villager_child_a', 'kid', pal)
    m = c.m
    L, K, T, hy, ytop, tw, ua, la = dims(c)

    c.legs('pants', 'shoe', boot_top=3)
    for s in SIDES:
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'Shin' and 3 <= y < 6, 'sock')
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'Shin' and y >= 6, 'skin')
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'Thigh' and y == K, c.t('pants', 0.86))
    c.rect(2, 4, K + 2, K + 4, 1, 'patch')
    c.rect(-4, -2, K - 1, K, 1, 'plaster')
    c.torso_paint('shirt')
    c.paint_where(lambda x, y, z, b, col: b == 'Hips' and y in (L + 1, L + 2), 'shirt')
    for y in (L + 1, L + 2):                                     # flared tunic hem
        for x in range(-6, 6):
            for z in range(-4, 4):
                if x in (-6, 5) or z in (-4, 3):
                    if (x in (-6, 5)) and (z in (-4, 3)):
                        continue
                    m.put(x, y, z, 'shirt_dk' if y == L + 1 else 'shirt', 'Hips', 1.0)
    c.arms_paint(upper='shirt', upper_rows=(0, 3))
    for s in SIDES:
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'UpperArm' and y == T - 3, 'shirt_dk')
    c.rect(-2, 2, T - 1, T, 2, 'skin')                           # round neckline with a lace tie
    c.rect(-1, 1, T - 2, T - 1, 2, 'skin')
    c.rect(-1, 1, T - 3, T - 2, 2, 'lace', 0)
    c.belt(L + 3)
    c.face(brow=('hair', 2, 1), nose=1)
    ey = c.eye_y
    for (x, y) in ((-6, ey - 1), (-5, ey - 2), (4, ey - 1), (5, ey - 2)):
        m.paint(x, y, 5, 'freckle', 0)
    c.ears()
    c.hair('hair', side_bottom=6, back_bottom=2, sideburn=4,
           bangs=[3, 3, 4, 3, 2, 3, 4, 2, 3, 4, 3, 2, 3, 4, 3, 3],
           tufts=[(-5, 3, 0), (-3, 3, 2), (-1, 3, -2), (1, 3, 1), (3, 3, -1), (4, 3, 3), (-2, 3, -4),
                  (2, 3, -5), (-6, 3, -2), (-3, 4, 2), (1, 4, 1), (-1, 4, -2)])
    for y in range(L - 1, L + 2):                                # slingshot in the back pocket
        m.put(3, y, -4, 'wood', 'Hips', 1.0)
    for y in (L + 2, L + 3):
        m.put(2, y, -4, 'wood', 'Hips', 1.0)
        m.put(4, y, -4, 'wood', 'Hips', 1.0)
    return c


# ====================================================================== 5. villager_child_b
def villager_child_b():
    pal = dict(skin='#f6c8a8', hair='#5e3a24', iris='#4a3323', shirt='#e59fa2', skirt='#d1848c',
               apron='#f3e6cf', ribbon='#d9606e', shoe='#6b4a30', sock='#fff8ee', belt='#b0705f',
               metal='#aa8e4b', collar='#f7ecdb')
    c = Char('villager_child_b', 'kid', pal)
    m = c.m
    L, K, T, hy, ytop, tw, ua, la = dims(c)

    c.legs('skirt', 'shoe', boot_top=3)
    for s in SIDES:
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'Shin' and 3 <= y < 6, 'sock')
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'Shin' and y >= 6, 'skin')
    c.torso_paint('shirt')
    c.paint_where(lambda x, y, z, b, col: b == 'Hips' and y == L + 2, 'skirt')
    c.arms_paint(upper='shirt', upper_rows=(0, 3))
    for s in SIDES:                                              # puffed sleeves
        x0, x1 = xr(s, tw + 3, tw + 4)
        for y in range(T - 3, T):
            for z in range(-2, 1):
                m.put(x0, y, z, 'shirt', s + 'UpperArm', 1.0)
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'UpperArm' and y == T - 3, c.t('shirt', 0.86))
    c.skirt(L + 2, K, (6.5, 4.5), (8.5, 6.5), 'skirt', trim='apron', trim_rows=1)
    c.paint_where(lambda x, y, z, b, col: b == 'Skirt' and K < y <= L + 2 and z >= 3 and -4 <= x <= 3, 'apron')
    for y in range(L + 3, T - 2):                                # apron bib
        for x in range(-3, 3):
            c.ov(x, y, 3, 'apron')
    for x in (-3, 2):
        for y in (T - 2, T - 1):
            m.paint(x, y, 2, 'apron')
        for z in range(-3, 3):
            m.paint(x, T - 1, z, 'apron')
        for y in range(L + 3, T - 1):
            m.paint(x, y, -3, 'apron')
    c.rect(-2, 2, T - 1, T, 2, 'collar')
    for x in range(-5, 5):                                       # waist sash and bow
        for y in (L + 3,):
            m.paint(x, y, -3, 'ribbon')
    c.paint_where(lambda x, y, z, b, col: b == 'Spine' and y == L + 3, 'ribbon')
    for x in range(-3, 3):
        c.ov(x, L + 3, 3, 'ribbon')
    for (x, y) in ((-1, L + 3), (0, L + 3), (-3, L + 4), (-2, L + 4), (1, L + 4), (2, L + 4),
                   (-3, L + 3), (-2, L + 3), (1, L + 3), (2, L + 3), (-2, L + 2), (1, L + 1)):
        c.ov(x, y, -4, 'ribbon' if x in (-1, 0) else c.t('ribbon', 0.92))
    c.face(brow=('hair', 2, 1), nose=1)
    c.hair('hair', side_bottom=3, back_bottom=0,
           bangs=[4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4])
    for s in SIDES:                                              # pigtails with ribbons
        g = 1 if s == 'L' else -1
        xa, xb = xr(s, 8, 11)
        xc, xd = xr(s, 9, 11)
        c.tail_chain(s + 'Tail', 'Head',
                     [(g * 9.5, hy + 9, -2.5), (g * 9.5, hy + 5, -2.5)],
                     [[(xa, xb, hy + 5, hy + 9, -4, -1, 'hair'), (xa, xb, hy + 9, hy + 11, -4, -1, 'ribbon')],
                      [(xc, xd, hy, hy + 5, -4, -1, 'hair')]], gain=1.0)
    return c


# ====================================================================== 6. villager_woman_a
def villager_woman_a():
    pal = dict(skin='#eebb9a', hair='#77492a', iris='#4b6a3a', top='#b1544a', skirt='#a4463c', hem='#86342d',
               apron='#f1e7cd', belt='#8a5a3a', metal='#aa8e4b', shoe='#5a3f2b', collar='#f1e7cd', pin='#c9b25a')
    c = Char('villager_woman_a', 'woman', pal)
    m = c.m
    L, K, T, hy, ytop, tw, ua, la = dims(c)

    c.legs('skirt', 'shoe', boot_top=5)
    c.torso_paint('top')
    c.paint_where(lambda x, y, z, b, col: b == 'Hips' and y == L + 2, 'skirt')
    c.arms_paint(upper='top', lower='top')
    y_end = T - ua - la
    for s in SIDES:                                              # three-quarter sleeves with a cuff
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'LowerArm' and y < y_end + 2, 'skin')
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'LowerArm' and y == y_end + 2, 'collar')
    c.skirt(L + 2, 5, (6.5, 4.5), (10, 8), 'skirt', trim='hem', trim_rows=2)
    c.paint_where(lambda x, y, z, b, col: b == 'Skirt' and 6 < y <= L + 2 and z >= 3 and -4 <= x <= 3, 'apron')
    c.paint_where(lambda x, y, z, b, col: b == 'Skirt' and y == 6 and z >= 3 and -4 <= x <= 3, c.t('apron', 0.88))
    for y in range(L + 3, T - 4):                                # apron bib and straps
        for x in (range(-3, 3) if y < T - 6 else range(-2, 2)):
            c.ov(x, y, 3, 'apron')
    for x in (-2, 1):
        for y in (T - 2, T - 1):
            m.paint(x, y, 2, 'apron')
        for z in range(-3, 3):
            m.paint(x, T - 1, z, 'apron')
        for y in range(L + 3, T - 1):
            m.paint(x, y, -3, 'apron')
    c.rect(-3, 3, T - 1, T, 2, 'collar')
    for x in (-2, 1):
        m.paint(x, T - 1, 2, 'apron')
    c.paint_where(lambda x, y, z, b, col: b == 'Spine' and y == L + 3, 'belt')
    for x in range(-3, 3):
        c.ov(x, L + 3, 3, 'belt')
    for y in (L + 3, L + 4):
        for x in (-1, 0):
            c.ov(x, y, 4, 'metal', 0)
    for (x, y) in ((-2, L + 2), (-2, L + 1), (1, L + 2), (1, L + 1)):   # bow of the apron strings
        c.ov(x, y, -4, 'apron')
    c.face(brow=('hair', 3, 1), nose=1)
    c.hair('hair', side_bottom=3, back_bottom=1,
           bangs=[3, 4, 4, 3, 3, 3, 2, 1, 1, 2, 3, 3, 3, 4, 4, 3])
    m.box(-3, 3, hy + 9, hy + 14, -10, -7, 'hair', 'Head', 1.0)  # bun
    m.box(-4, 4, hy + 10, hy + 13, -10, -7, 'hair', 'Head', 1.0)
    m.box(-2, 2, hy + 10, hy + 13, -11, -10, 'hair', 'Head', 1.0)
    m.put(3, hy + 12, -9, 'pin', 'Head', 0)
    m.put(4, hy + 12, -9, 'pin', 'Head', 0)
    return c


# ====================================================================== 7. villager_woman_b
def villager_woman_b():
    pal = dict(skin='#f0c1a2', hair='#4a3524', iris='#3d5a7a', shirt='#f2ead2', bodice='#3f5a74',
               skirt='#7e8a4e', trim='#e0d2ad', scarf='#48678a', belt='#6a5238', metal='#aa8e4b',
               shoe='#574029', pouch='#8a6a44', shoe_dk='#3f2d1c')
    c = Char('villager_woman_b', 'woman', pal, tw=5)
    m = c.m
    L, K, T, hy, ytop, tw, ua, la = dims(c)

    c.legs('skirt', 'shoe', boot_top=5)
    c.torso_paint('shirt')
    c.paint_where(lambda x, y, z, b, col: b in ('Hips', 'Spine', 'Chest') and L + 3 <= y < T - 3, 'bodice')
    c.paint_where(lambda x, y, z, b, col: b == 'Hips' and y == L + 2, 'skirt')
    c.arms_paint(upper='shirt', upper_rows=(0, ua))
    for s in SIDES:                                              # puffed sleeves, forearms bare with a band
        x0, x1 = xr(s, tw + 3, tw + 4)
        for y in range(T - 5, T):
            for z in range(-2, 1):
                m.put(x0, y, z, 'shirt', s + 'UpperArm', 1.0)
        c.paint_where(lambda x, y, z, b, col, s=s: b == s + 'UpperArm' and T - ua <= y < T - ua + 1, 'trim')
    for y in range(L + 4, T - 3, 2):                             # bodice lacing
        m.paint(-1, y, 2, 'trim', 0)
        m.paint(0, y + 1, 2, 'trim', 0) if y + 1 < T - 3 else None
    c.rect(-3, 3, T - 3, T - 2, 2, 'trim', 0.5)
    c.skirt(L + 2, 5, (6.5, 4.5), (10, 8), 'skirt', trim='trim', trim_rows=2)
    c.paint_where(lambda x, y, z, b, col: b in ('Spine',) and y == L + 3, 'belt')
    for x in range(-3, 3):
        c.ov(x, L + 3, 3, 'belt')
    for y in (L + 3, L + 4):
        for x in (-1, 0):
            c.ov(x, y, 4, 'metal', 0)
    for y in range(L - 1, L + 2):                                # herb pouch hanging from the belt
        zf = max(z for (x, yy, z), (col, b, j) in m.v.items() if yy == y and b == 'Skirt' and 2 <= x <= 4)
        for x in (2, 3, 4):
            for z in (zf + 1, zf + 2):
                m.put(x, y, z, c.t('pouch', 0.95 if y > L - 1 else 0.82), 'Hips', 1.0)
    m.put(3, L + 1, max(z for (x, yy, z), (col, b, j) in m.v.items() if yy == L + 1 and b == 'Skirt' and x == 3) + 1,
          'metal', 'Hips', 0)
    c.face(brow=('hair', 3, 1), nose=1)
    c.hair('hair', side_bottom=4, back_bottom=2, bangs=[0] * 16, top_layers=2)
    # blue headscarf over the crown with a cream band, a few wisps on the forehead
    for (x, y, z), (col, b, j) in list(m.v.items()):
        if b == 'Head' and (y > ytop - 2 and (z < 5 or y >= ytop)):
            m.v[(x, y, z)] = (c.t('scarf', 1.08 if y > ytop else 1.0), b, 1.0)
    for x in range(-7, 7):
        for y in (ytop - 1, ytop):
            m.paint(x, y, 5, 'scarf')
            m.put(x, y, 6, c.t('scarf', 0.9), 'Head', 1.0)
        m.paint(x, ytop - 2, 5, 'trim')
        m.put(x, ytop - 2, 6, 'trim', 'Head', 1.0)
    for z in range(-7, 6):
        for x in (-8, 7):
            m.put(x, ytop - 2, z, 'trim', 'Head', 1.0)
    for x in (-8, 7):
        for z in range(-7, 5):
            for y in (ytop - 1, ytop):
                m.put(x, y, z, c.t('scarf', 0.92), 'Head', 1.0)
    m.box(-2, 2, hy + 10, hy + 13, -10, -8, 'scarf', 'Head', 1.0)  # knot at the back
    m.box(-3, 3, hy + 10, hy + 12, -9, -8, c.t('scarf', 0.9), 'Head', 1.0)
    # braid hanging down the back
    c.tail_chain('Braid', 'Head',
                 [(0, hy + 8, -8), (0, hy + 1, -7), (0, hy - 4, -6)],
                 [[(-1, 1, hy + 1, hy + 8, -9, -7, 'hair')],
                  [(-1, 1, hy - 4, hy + 1, -8, -6, 'hair')],
                  [(-1, 1, hy - 9, hy - 4, -7, -5, 'hair'), (-1, 1, hy - 10, hy - 9, -7, -5, 'trim')]], gain=1.0)
    for bn in ('Braid1', 'Braid2', 'Braid3'):
        for (x, y, z), (col, b, j) in list(m.v.items()):
            if b == bn and (y + x) % 2 == 0:
                m.v[(x, y, z)] = (c.t('hair', 0.86), b, 1.0)
    return c


CHARACTERS = [villager, villager_man_a, villager_man_b, villager_child_a, villager_child_b,
              villager_woman_a, villager_woman_b]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'villagers_v2')
    only = sys.argv[2:] or None
    os.makedirs(out, exist_ok=True)
    for fn in CHARACTERS:
        if only and fn.__name__ not in only:
            continue
        c = fn()
        rig = c.rig()
        info = c.export(os.path.join(out, c.name + '.glb'), build_clips(c, rig))
        print(c.name, info)


if __name__ == '__main__':
    main()
