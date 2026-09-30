"""Animation library for the v2 voxel villagers.

Every clip is a function t -> Pose. Rotations are local Euler angles (x = pitch, y = yaw, z = roll):
  * forward flexion of a limb is a *negative* x rotation, knee flexion is a *positive* x rotation,
  * Pose.sym() takes z as "outward" so both sides can share one call,
  * feet are snapped to the ground automatically (see vox2.sample_clip).
"""
import math

import numpy as np

from vox2 import Pose, qmat
from voxlib import quat_euler

TAU = 2 * math.pi


def sstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def env(t, dur, a, b):
    """0 -> 1 in a seconds, hold, 1 -> 0 during the last b seconds."""
    return sstep(t / a) * sstep((dur - t) / b)


def pulse(t, c, hw):
    return sstep(1 - abs(t - c) / hw)


def blink(t, events, hw=0.085):
    return min(1.0, sum(pulse(t, c, hw) for c in events))


# ---------------------------------------------------------------- arm reach solver
class Reach:
    """Finds arm angles (upper x/z, lower x/z) that put the hand centre on a target (left arm frame)."""

    def __init__(self, ch, rig):
        self.rig, self.d = rig, ch.d
        self.cache = {}
        ux = np.arange(-2.9, 0.7, 0.1)
        uz = np.arange(-0.9, 2.3, 0.1)
        lx = np.arange(-2.9, 0.15, 0.1)
        lz = np.arange(-1.0, 1.05, 0.1)
        self.ux, self.uz, self.lx, self.lz = ux, uz, lx, lz

        def rx(a):
            c, s = np.cos(a), np.sin(a)
            m = np.zeros((len(a), 3, 3))
            m[:, 0, 0] = 1
            m[:, 1, 1] = c
            m[:, 1, 2] = -s
            m[:, 2, 1] = s
            m[:, 2, 2] = c
            return m

        def rz(a):
            c, s = np.cos(a), np.sin(a)
            m = np.zeros((len(a), 3, 3))
            m[:, 2, 2] = 1
            m[:, 0, 0] = c
            m[:, 0, 1] = -s
            m[:, 1, 0] = s
            m[:, 1, 1] = c
            return m
        # R1 = Rx(ux) Rz(uz), R2 = R1 Rx(lx) Rz(lz)   (matches quat_euler with y = 0)
        self.R1 = np.einsum('aij,bjk->abik', rx(ux), rz(uz))                 # (nux, nuz, 3, 3)
        self.RL = np.einsum('aij,bjk->abik', rx(lx), rz(lz))                 # (nlx, nlz, 3, 3)

    def solve(self, target, pref=(0.0, 0.1, -0.2, 0.0), tw=None):
        """target: (x, y, z) in voxel units for the LEFT hand (mirror x for the right one)."""
        key = tuple(round(float(v), 2) for v in target) + tuple(pref)
        if key in self.cache:
            return self.cache[key]
        d = self.d
        P0 = self.rig.pivot['LUpperArm']
        P1 = self.rig.pivot['LLowerArm']
        P2 = self.rig.pivot['LHand']
        R1 = self.R1                                     # (a, b, 3, 3)
        elbow = P0 + np.einsum('abij,j->abi', R1, P1 - P0)   # (a, b, 3)
        R2 = np.einsum('abij,cdjk->abcdik', R1, self.RL)     # (a, b, c, d, 3, 3)
        wrist = elbow[:, :, None, None, :] + np.einsum('abcdij,j->abcdi', R2, P2 - P1)
        hand = wrist + np.einsum('abcdij,j->abcdi', R2, np.array([0.0, -1.5, 0.0]))
        err = np.sum((hand - np.asarray(target)) ** 2, axis=-1)
        # regularise towards a natural arm and keep the elbow low and the hand out of the torso
        ux, uz, lx, lz = np.meshgrid(self.ux, self.uz, self.lx, self.lz, indexing='ij')
        cost = err + 0.4 * ((ux - pref[0]) ** 2 + (uz - pref[1]) ** 2 + (lx - pref[2]) ** 2 + (lz - pref[3]) ** 2)
        ey = elbow[:, :, 1][:, :, None, None]
        cost = cost + 30.0 * np.maximum(0.0, ey - (P0[1] - 1.0)) ** 2
        twh = d['tw']
        inside = (np.abs(hand[..., 0] + 0.5) < twh + 0.5) & (np.abs(hand[..., 2] + 0.5) < 3.5) & \
                 (hand[..., 1] < d['T']) & (hand[..., 1] > d['L'] + 1)
        cost = cost + 200.0 * inside
        i = np.unravel_index(np.argmin(cost), cost.shape)
        res = (float(self.ux[i[0]]), float(self.uz[i[1]]), float(self.lx[i[2]]), float(self.lz[i[3]]),
               float(np.sqrt(err[i])))
        self.cache[key] = res
        return res


# ---------------------------------------------------------------- clips
def build_clips(ch, rig):
    kind, skirt, d = ch.kind, ch.has_skirt, ch.d
    kid = kind == 'kid'
    T, hy, ua, la = d['T'], d['hy'], d['ua'], d['la']
    reach = Reach(ch, rig)

    def arm(p, side, part, x=0.0, y=0.0, z=0.0):
        """z > 0 = outward for either side."""
        g = 1 if side == 'L' else -1
        p.add(side + part, x, g * y, g * z)

    def relax(p, k=1.0):
        p.sym('UpperArm', x=-0.05, z=0.07 * k)
        p.sym('LowerArm', x=-0.16 * k)
        p.sym('Hand', x=-0.05)

    def reach_to(p, side, target, w=1.0, pref=(0.0, 0.1, -0.2, 0.0)):
        """Blend the arm towards the pose that puts the hand on target (given for the LEFT hand)."""
        tx = target[0] if side == 'L' else -target[0]
        # solver works in the left frame -> use |x|
        ux, uz, lx, lz, err = reach.solve((abs(tx), target[1], target[2]), pref)
        g = 1 if side == 'L' else -1
        p.add(side + 'UpperArm', ux * w, 0, g * uz * w)
        p.add(side + 'LowerArm', lx * w, 0, g * lz * w)

    tails = ch.tails

    def with_tails(fn, dur, loop):
        if not tails:
            return fn

        def cum(p):
            pi = sum(p.get(b)[0] for b in ('Hips', 'Spine', 'Chest', 'Neck', 'Head'))
            ro = sum(p.get(b)[2] for b in ('Hips', 'Spine', 'Chest', 'Neck', 'Head'))
            return pi, ro

        def g(t):
            p = fn(t)
            pis, ros = [], []
            for k in range(4):
                tt = t - 0.045 * k
                tt = tt % dur if loop else max(0.0, tt)
                q = p if k == 0 else fn(tt)
                a, b = cum(q)
                pis.append(a)
                ros.append(b)
            pl, rl = sum(pis) / 4, sum(ros) / 4
            for i, (bn, gain) in enumerate(tails):
                sway = 0.05 * math.sin(TAU * t / dur * (1 if loop else 0) + i * 1.3)
                p.add(bn, -gain * pl * 0.92 + sway, 0, -gain * rl * 0.9)
            return p
        return g

    # ------------------------------------------------ Idle
    def idle(t):
        dur = 4.0
        p = Pose()
        ph = TAU * t / dur
        b = math.sin(ph)
        relax(p)
        p.add('Chest', 0.022 * b)
        p.add('Spine', 0.008 * b - 0.01)
        p.add('Head', -0.02 * b, 0.14 * math.sin(ph + 0.5) + 0.05 * math.sin(2 * ph), 0.02 * math.sin(ph))
        p.add('Hips', 0, 0.03 * math.sin(ph), 0.022 * math.sin(ph))
        p.add('Spine', 0, 0, -0.02 * math.sin(ph))
        p.sym('UpperArm', z=0.014 * b)
        p.sym('LowerArm', x=-0.02 * b)
        p.off[0] = 0.18 * math.sin(ph)
        p.blink = blink(t, [1.3, 1.56, 3.1])
        return p

    # ------------------------------------------------ Walk / Run
    def locomotion(t, dur, run=False):
        p = Pose()
        ph = TAU * t / dur
        s, co = math.sin(ph), math.cos(ph)
        if run:
            A = 0.92 if not skirt else 0.5
            B, C, lean = (1.75 if not skirt else 1.3), 0.95, 0.26
        else:
            A = (0.50 if not kid else 0.52) if not skirt else 0.36
            B, C, lean = (0.78 if not skirt else 0.6), (0.44 if not skirt else 0.36), 0.05
        for side, g in (('L', 1), ('R', -1)):
            sl, cl = g * s, g * co
            th = -A * sl
            kn = B * max(0.0, cl) + (0.16 if run else 0.06)
            p.add(side + 'Thigh', th)
            p.add(side + 'Shin', kn)
            p.add(side + 'Foot', -(th + kn) * (0.62 if run else 0.92) + (0.42 if run else 0.3) * max(0.0, -sl) ** 2)
            arm(p, side, 'UpperArm', C * g * s * (1 if side == 'L' else 1))
        # arms swing opposite to the same-side leg: left arm forward when the left leg is back
        # (recompute cleanly)
        p.r['LUpperArm'] = (C * s, 0, 0)
        p.r['RUpperArm'] = (-C * s, 0, 0)
        if run:
            p.add('LLowerArm', -(1.35 + 0.35 * max(0.0, -s)))
            p.add('RLowerArm', -(1.35 + 0.35 * max(0.0, s)))
            p.sym('UpperArm', z=0.12)
            p.sym('Hand', x=-0.2)
            p.add('Spine', lean)
            p.add('Chest', 0.04)
            p.add('Head', -0.24)
            p.add('Chest', 0, -0.26 * s)
            p.add('Hips', 0, 0.16 * s, 0.05 * co)
            p.lift = (3.0 if not kid else 2.3) * (0.5 - 0.5 * math.cos(2 * ph))
            p.off[0] = 0.3 * math.sin(ph + 1.57)
        else:
            p.add('LLowerArm', -(0.22 + 0.45 * max(0.0, -s)))
            p.add('RLowerArm', -(0.22 + 0.45 * max(0.0, s)))
            p.sym('UpperArm', z=0.07)
            p.sym('Hand', x=-0.05)
            p.add('Spine', lean)
            p.add('Head', -0.04)
            p.add('Chest', 0, -0.15 * s)
            p.add('Hips', 0, 0.1 * s, 0.035 * co)
            p.add('Head', 0, 0.06 * s)
            p.off[0] = 0.32 * math.sin(ph + 1.57)
        p.blink = blink(t, [dur * 0.62])
        return p

    wd = 0.8 if kid else 1.0
    rd = 0.5 if kid else 0.6

    # ------------------------------------------------ Wave
    def wave(t):
        dur = 2.0
        p = Pose()
        relax(p)
        e = env(t, dur, 0.4, 0.4)
        w = math.sin(TAU * 3 * t / dur)
        p.add('RUpperArm', -0.12 * e, 0, -1.95 * e)
        p.add('RLowerArm', -0.15 * e, 0, -(0.55 + 0.42 * w) * e)
        p.add('RHand', 0, 0, -0.25 * w * e)
        p.add('Chest', 0, -0.08 * e, 0.05 * e)
        p.add('Head', -0.03 * e, -0.16 * e, 0.09 * e)
        p.add('Spine', 0, 0, 0.03 * e)
        p.add('Hips', 0, 0, 0.03 * math.sin(TAU * t / dur))
        p.blink = blink(t, [0.85, 1.75])
        return p

    # ------------------------------------------------ Nod / ShakeHead
    def nod(t):
        dur = 1.2
        p = Pose()
        relax(p)
        e = env(t, dur, 0.1, 0.2)
        n = max(0.0, math.sin(TAU * 2 * t / dur))
        p.add('Head', 0.34 * n * e)
        p.add('Neck', 0.1 * n * e)
        p.add('Chest', 0.05 * n * e)
        p.blink = blink(t, [0.42])
        return p

    def shake(t):
        dur = 1.4
        p = Pose()
        relax(p)
        e = env(t, dur, 0.15, 0.25)
        n = math.sin(TAU * 2.5 * t / dur)
        p.add('Head', 0.04 * e, 0.42 * n * e, 0.03 * n * e)
        p.add('Neck', 0, 0.12 * n * e)
        p.add('Chest', 0, -0.06 * n * e)
        p.blink = blink(t, [1.0])
        return p

    # ------------------------------------------------ Bow
    def bow(t):
        dur = 2.2
        p = Pose()
        relax(p)
        e = sstep(t / 0.75) * sstep((dur - t) / 0.75)
        p.add('Spine', 0.46 * e)
        p.add('Chest', 0.16 * e)
        p.add('Neck', 0.04 * e)
        p.add('Head', 0.06 * e)
        p.sym('UpperArm', x=-0.28 * e, z=-0.06 * e)
        p.sym('LowerArm', x=-0.1 * e)
        p.sym('Hand', z=-0.1 * e)
        p.add('LThigh', -0.06 * e)
        p.add('RThigh', -0.06 * e)
        p.add('LShin', 0.06 * e)
        p.add('RShin', 0.06 * e)
        p.blink = blink(t, [0.9 + 0.0]) * 0 + (0.85 * e if 0.7 < t < 1.6 else 0.0)
        return p

    # ------------------------------------------------ Pray
    def pray(t):
        dur = 3.0
        p = Pose()
        relax(p)
        e = env(t, dur, 0.7, 0.7)
        b = math.sin(TAU * t / dur)
        for side in 'LR':
            reach_to(p, side, (0.9, T - 5.5, 4.2), e, pref=(-0.5, -0.2, -1.7, 0.0))
        p.add('Head', 0.2 * e, 0, 0.03 * e)
        p.add('Neck', 0.06 * e)
        p.add('Chest', 0.06 * e + 0.015 * b * e)
        p.add('Spine', 0.04 * e)
        p.blink = 1.0 * sstep((t - 0.55) / 0.2) * sstep((dur - 0.6 - t) / 0.2)
        return p

    # ------------------------------------------------ Surprise
    def surprise(t):
        dur = 1.4
        p = Pose()
        relax(p)
        e = sstep(t / 0.09) * sstep((dur - t) / 0.55)
        p.add('Spine', -0.16 * e)
        p.add('Chest', -0.12 * e)
        p.add('Head', -0.2 * e)
        p.sym('UpperArm', x=-0.5 * e, z=0.85 * e)
        p.sym('LowerArm', x=-1.05 * e)
        p.sym('Hand', x=-0.3 * e)
        p.add('LThigh', -0.1 * e)
        p.add('LShin', 0.12 * e)
        p.add('RThigh', 0.16 * e)
        p.add('RShin', 0.06 * e)
        p.lift = 1.6 * math.sin(math.pi * min(1.0, t / 0.28)) * (1 if t < 0.28 else 0)
        return p

    # ------------------------------------------------ Joy
    def joy(t):
        dur = 2.0
        p = Pose()
        relax(p)
        e = env(t, dur, 0.2, 0.3)
        u = math.sin(TAU * t / 1.0)
        air, cr = max(0.0, u), max(0.0, -u)
        p.lift = (4.5 if not kid else 3.5) * e * air ** 0.85
        for side in 'LR':
            p.add(side + 'Thigh', (-0.5 * cr + -0.25 * air) * e)
            p.add(side + 'Shin', (1.0 * cr + 0.6 * air) * e)
            p.add(side + 'Foot', (-0.4 * cr + 0.2 * air) * e)
        w = math.sin(TAU * 3 * t / dur)
        p.sym('UpperArm', x=-0.15 * e, z=(0.15 + 2.3 * air ** 0.5 * e + 0.5 * cr * e))
        p.sym('LowerArm', x=-0.2 * e, z=(0.3 + 0.15 * w) * e)
        p.add('Head', -0.15 * e * air, 0.0, 0.05 * w * e)
        p.add('Spine', 0.12 * e * cr - 0.08 * e * air)
        p.blink = blink(t, [1.55])
        return p

    # ------------------------------------------------ Shy
    def shy(t):
        dur = 2.6
        p = Pose()
        relax(p)
        e = env(t, dur, 0.6, 0.6)
        ph = TAU * t / dur
        for side in 'LR':
            reach_to(p, side, (0.9, T - 12, 4.3), e, pref=(-0.3, -0.1, -0.5, 0.0))
        p.add('Head', 0.26 * e, 0.4 * e, 0.16 * e)
        p.add('Neck', 0.06 * e, 0.1 * e)
        p.add('Chest', 0.11 * e, -0.1 * e, 0.03 * e)
        p.add('Hips', 0, 0.08 * math.sin(ph) * e, 0.06 * e)
        p.add('LThigh', 0, -0.14 * e)
        p.add('RThigh', 0, 0.06 * e)
        p.add('RShin', 0.12 * e)
        p.sym('UpperArm', x=0.0, z=-0.05 * e)
        p.blink = blink(t, [1.0, 1.9])
        return p

    # ------------------------------------------------ Hurt
    def hurt(t):
        dur = 1.2
        p = Pose()
        relax(p)
        e = (t / 0.07) if t < 0.07 else ((dur - t) / (dur - 0.07)) ** 2
        p.add('Spine', -0.3 * e)
        p.add('Chest', -0.14 * e)
        p.add('Head', -0.28 * e, 0.0, 0.16 * e)
        p.sym('UpperArm', x=-0.5 * e, z=0.35 * e)
        p.sym('LowerArm', x=-0.95 * e)
        for side in 'LR':
            p.add(side + 'Thigh', -0.16 * e)
            p.add(side + 'Shin', 0.34 * e)
            p.add(side + 'Foot', -0.14 * e)
        p.off[2] = -1.2 * e
        p.blink = 1.0 if 0.04 < t < 0.55 else 0.0
        return p

    # ------------------------------------------------ Talk
    def talk(t):
        dur = 2.4
        p = Pose()
        relax(p)
        ph = TAU * t / dur
        p.add('RUpperArm', -0.42 + 0.14 * math.sin(ph), 0, -0.16 - 0.1 * math.sin(2 * ph))
        p.add('RLowerArm', -0.95 - 0.3 * math.sin(2 * ph + 0.5), 0, -0.1)
        p.add('RHand', 0.15 * math.sin(3 * ph), 0.25, -0.15 + 0.2 * math.sin(2 * ph + 1))
        p.add('LUpperArm', -0.14 - 0.08 * math.sin(ph + 2))
        p.add('LLowerArm', -0.3 - 0.25 * max(0.0, math.sin(ph + 2)))
        p.add('Head', 0.05 * math.sin(3 * ph) - 0.02, 0.14 * math.sin(ph), 0.03 * math.sin(ph))
        p.add('Chest', 0.02, 0.07 * math.sin(ph))
        p.add('Hips', 0, 0, 0.02 * math.sin(ph))
        p.blink = blink(t, [0.7, 1.75])
        return p

    # ------------------------------------------------ Sad
    def sad(t):
        dur = 3.2
        p = Pose()
        relax(p, 0.4)
        ph = TAU * t / dur
        b = math.sin(ph)
        sob = math.sin(TAU * 4 * t / dur) * pulse(t, 2.1, 0.5)
        p.add('Head', 0.3 + 0.02 * b + 0.03 * sob, 0.06 * math.sin(ph), 0.06)
        p.add('Neck', 0.06)
        p.add('Chest', 0.1 + 0.02 * b + 0.03 * sob)
        p.add('Spine', 0.04)
        p.sym('UpperArm', x=0.06, z=-0.02)
        p.sym('LowerArm', x=-0.1)
        p.sym('Hand', x=0.05)
        p.blink = blink(t, [1.2, 2.5, 2.75])
        return p

    # ------------------------------------------------ Clap
    def clap(t):
        dur = 1.6
        p = Pose()
        relax(p)
        e = env(t, dur, 0.25, 0.25)
        c = max(0.0, math.cos(TAU * 3 * t / dur)) ** 3      # 1 = hands together
        for side in 'LR':
            reach_to(p, side, (0.6 + 5.4 * (1 - c), T - 4.5, 4.4 - 1.4 * (1 - c)), e,
                     pref=(-0.7, 0.0, -1.5, 0.0))
        p.add('Head', -0.04 * e)
        p.add('Chest', 0.02 * e * c)
        p.blink = blink(t, [0.8])
        return p

    # ------------------------------------------------ Point
    def point(t):
        dur = 1.8
        p = Pose()
        relax(p)
        e = env(t, dur, 0.4, 0.4)
        p.add('RUpperArm', -1.5 * e, 0, -0.12 * e)
        p.add('RLowerArm', -0.06 * e)
        p.add('Head', 0, -0.18 * e)
        p.add('Chest', 0, -0.14 * e)
        p.add('Spine', 0.03 * e)
        p.blink = blink(t, [1.2])
        return p

    # ------------------------------------------------ Panic (frantic run on the spot)
    def panic(t):
        dur = 0.8
        p = Pose()
        ph = TAU * t / dur
        s, co = math.sin(ph), math.cos(ph)
        A = 0.75 if not skirt else 0.58
        for side, g in (('L', 1), ('R', -1)):
            sl, cl = g * s, g * co
            th = -A * sl
            kn = 1.5 * max(0.0, cl) + 0.14
            p.add(side + 'Thigh', th)
            p.add(side + 'Shin', kn)
            p.add(side + 'Foot', -(th + kn) * 0.6 + 0.35 * max(0.0, -sl) ** 2)
        p.sym('UpperArm', x=-0.35, z=1.9)
        p.add('LUpperArm', 0.0, 0, 0.25 * s)
        p.add('RUpperArm', 0.0, 0, -0.25 * s)
        p.sym('LowerArm', x=-0.3 + 0.0, z=0.7)
        p.add('LLowerArm', 0.5 * s)
        p.add('RLowerArm', -0.5 * s)
        p.add('Spine', 0.1)
        p.add('Head', -0.1, 0.24 * math.sin(2 * ph), 0.1 * math.sin(2 * ph + 1))
        p.add('Chest', 0, -0.2 * s)
        p.add('Hips', 0, 0.12 * s, 0.05 * co)
        p.lift = 2.0 * (0.5 - 0.5 * math.cos(2 * ph))
        p.blink = 0.0
        return p

    # ------------------------------------------------ Cower
    def cower(t):
        dur = 2.4
        p = Pose()
        relax(p)
        e = sstep(t / 0.5) * sstep((dur - t) / 0.5)
        tr = math.sin(TAU * 9 * t / dur) * 0.03 * e
        for side in 'LR':
            p.add(side + 'Thigh', -(1.15 if not skirt else 0.7) * e)
            p.add(side + 'Shin', (1.75 if not skirt else 1.1) * e)
            p.add(side + 'Foot', -(0.6 if not skirt else 0.4) * e)
            reach_to(p, side, (5.5, min(hy + 8, T - 1.5 + 0.8 * (ua + la + 1.5)), 2.5), e, pref=(-1.5, 0.3, -1.6, 0.0))
        p.add('Spine', 0.5 * e + tr)
        p.add('Chest', 0.16 * e - tr)
        p.add('Head', 0.05 * e + tr, 0.05 * math.sin(TAU * t / dur) * e)
        p.blink = min(1.0, 1.0 * sstep((t - 0.3) / 0.15) * sstep((dur - 0.3 - t) / 0.15))
        p.ground = 'feet'
        return p

    # ------------------------------------------------ Defeat (one shot: recoil, drop to the knees, slump)
    def defeat(t):
        dur = 3.0
        p = Pose()
        relax(p, 0.5)
        a = sstep(t / 0.4)
        k = sstep((t - 0.35) / 0.9)
        s = sstep((t - 1.2) / 1.1)
        b = math.sin(TAU * (t - 2.2) / 2.0) * sstep((t - 2.2) / 0.4)
        p.add('Spine', -0.3 * a * (1 - k) + 0.5 * s)
        p.add('Chest', -0.15 * a * (1 - k) + 0.25 * s + 0.015 * b)
        p.add('Head', -0.3 * a * (1 - k) + 0.3 * s, 0.0, 0.09 * s)
        for side in 'LR':
            p.add(side + 'Thigh', -0.08 * k)
            p.add(side + 'Shin', 1.5 * k)
            p.add(side + 'Foot', 0.55 * k)
        p.sym('UpperArm', x=-0.45 * a * (1 - k) + 0.1 * k - 0.25 * s, z=0.5 * a * (1 - k) + 0.08 * k)
        p.sym('LowerArm', x=-0.4 * a * (1 - k) - 0.15 * s)
        p.ground = 'body'
        p.blink = 1.0 * sstep((t - 0.5) / 0.25)
        return p

    specs = [
        ('Idle', 4.0, True, idle),
        ('Walk', wd, True, lambda t: locomotion(t, wd)),
        ('Run', rd, True, lambda t: locomotion(t, rd, True)),
        ('Wave', 2.0, False, wave),
        ('Nod', 1.2, False, nod),
        ('Bow', 2.2, False, bow),
        ('Pray', 3.0, False, pray),
        ('Surprise', 1.4, False, surprise),
        ('Joy', 2.0, False, joy),
        ('Shy', 2.6, False, shy),
        ('Hurt', 1.2, False, hurt),
        ('ShakeHead', 1.4, False, shake),
        ('Talk', 2.4, True, talk),
        ('Sad', 3.2, True, sad),
        ('Clap', 1.6, True, clap),
        ('Point', 1.8, False, point),
        ('Panic', 0.8, True, panic),
        ('Cower', 2.4, False, cower),
        ('Defeat', 3.0, False, defeat),
    ]
    return [(n, dur, with_tails(fn, dur, loop)) for (n, dur, loop, fn) in specs]
