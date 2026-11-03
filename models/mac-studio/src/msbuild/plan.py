import math
import numpy as np
from . import dims as D


class PlanLoop:
    def __init__(self, half=D.HALF, R=D.CORNER_R, n=D.CORNER_N, dense=6000):
        self.half, self.R, self.n = half, R, n
        h, r = half, R
        t = np.linspace(0, np.pi / 2, dense)
        cu = np.cos(t) ** (2.0 / n)
        su = np.sin(t) ** (2.0 / n)
        c_pp = np.stack([h - r + r * cu, h - r + r * su], 1)
        rot = lambda p, k: p @ np.linalg.matrix_power(np.array([[0, 1], [-1, 0]]), k)
        c_mp = rot(c_pp, 1)
        c_mm = rot(c_pp, 2)
        c_pm = rot(c_pp, 3)
        m = 400
        rear_l = np.stack([np.linspace(0, -(h - r), m), np.full(m, h)], 1)
        left = np.stack([np.full(2 * m, -h), np.linspace(h - r, -(h - r), 2 * m)], 1)
        front = np.stack([np.linspace(-(h - r), h - r, 2 * m), np.full(2 * m, -h)], 1)
        right = np.stack([np.full(2 * m, h), np.linspace(-(h - r), h - r, 2 * m)], 1)
        rear_r = np.stack([np.linspace(h - r, 0, m), np.full(m, h)], 1)
        segs = [rear_l, c_mp, left, c_mm, front, c_pm, right, c_pp, rear_r]
        pts = [segs[0]]
        for s in segs[1:]:
            pts.append(s[1:] if np.linalg.norm(s[0] - pts[-1][-1]) < 1e-9 else s)
        P = np.vstack(pts)
        if np.linalg.norm(P[0] - P[-1]) < 1e-9:
            P = P[:-1]
        seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
        keep = seg > 1e-9
        P = P[keep]
        seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
        self.P = P
        self.s = np.concatenate([[0], np.cumsum(seg)[:-1]])
        self.L = float(np.sum(seg))
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
        T /= np.linalg.norm(T, axis=1)[:, None]
        self.T = T
        self.N = np.stack([T[:, 1], -T[:, 0]], 1)

    def eval(self, s):
        s = np.mod(np.asarray(s, dtype=np.float64), self.L)
        sp = np.concatenate([self.s, [self.L]])
        Pp = np.vstack([self.P, self.P[:1]])
        Np = np.vstack([self.N, self.N[:1]])
        x = np.interp(s, sp, Pp[:, 0])
        y = np.interp(s, sp, Pp[:, 1])
        nx = np.interp(s, sp, Np[:, 0])
        ny = np.interp(s, sp, Np[:, 1])
        nn = np.sqrt(nx * nx + ny * ny)
        return np.stack([x, y], -1), np.stack([nx / nn, ny / nn], -1)

    def sample(self, count, s0=0.0):
        s = s0 + np.arange(count) * (self.L / count)
        return self.eval(s)

    def sample_adaptive(self, ds_flat=1.5, ds_curve=0.6):
        out = [0.0]
        s = 0.0
        while True:
            p, nrm = self.eval(np.array([s]))
            q, nrm2 = self.eval(np.array([s + 0.3]))
            curv = math.acos(max(-1.0, min(1.0, float(np.dot(nrm[0], nrm2[0]))))) / 0.3
            step = ds_curve if curv > 1e-3 else ds_flat
            s += step
            if s >= self.L - step * 0.5:
                break
            out.append(s)
        return np.array(out)

    def offset_polar(self, d, angles):
        P = self.P - d * self.N
        ang = np.arctan2(P[:, 1], P[:, 0])
        rad = np.hypot(P[:, 0], P[:, 1])
        order = np.argsort(ang)
        ang = ang[order]
        rad = rad[order]
        ang = np.concatenate([ang[-1:] - 2 * np.pi, ang, ang[:1] + 2 * np.pi])
        rad = np.concatenate([rad[-1:], rad, rad[:1]])
        a = np.mod(np.asarray(angles) + np.pi, 2 * np.pi) - np.pi
        return np.interp(a, ang, rad)

    def s_of_rear_u(self, u):
        return self._s_of_x_on_side(D.HALF - u, side='rear')

    def _s_of_x_on_side(self, x, side):
        if side == 'rear':
            return np.mod(-x, self.L) if x <= 0 else self.L - x
        raise ValueError(side)

    def s_at_point(self, xy):
        d = np.linalg.norm(self.P - np.asarray(xy)[None, :], axis=1)
        return float(self.s[int(np.argmin(d))])
