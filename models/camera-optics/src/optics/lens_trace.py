"""Read a lens prescription (Largan-style tables) from a Google Patents page and ray-trace it in 2D.

uv run --with beautifulsoup4 --with numpy --with matplotlib python 工具/lens_trace.py <patent.html> [embodiment] [out.png]

Checks the trace against the patent's own f, Fno and HFOV, then draws the cross-section with rays.
Sag: z(y) = (y^2/R) / (1 + sqrt(1 - (1+k)(y/R)^2)) + sum A_i y^i  (i = 4, 6, ... 16), Largan's convention.
"""
import math, re, sys
import numpy as np
from bs4 import BeautifulSoup

ORD = {1: '1st', 2: '2nd', 3: '3rd'}


def table_rows(html):
    soup = BeautifulSoup(open(html, encoding='utf-8').read(), 'html.parser')
    desc = soup.find('section', itemprop='description') or soup
    rows = []
    for t in desc.find_all('table'):
        for tr in t.find_all('tr'):
            cells = [re.sub(r'\s+', ' ', c.get_text(' ', strip=True)).replace('−', '-')
                     for c in tr.find_all(['td', 'th'])]
            if any(cells):
                rows.append(cells)
    return rows


def num(s):
    s = s.replace('E', 'e').strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse(html, emb=1):
    rows = table_rows(html)
    tag = f'{ORD.get(emb, str(emb) + "th")} Embodiment'
    i = next(k for k, r in enumerate(rows) if any(tag in c for c in r))
    head = ' '.join(rows[i] + rows[i + 1])
    f = float(re.search(r'f = ([\d.]+)', head).group(1))
    fno = float(re.search(r'Fno = ([\d.]+)', head).group(1))
    hfov = float(re.search(r'HFOV = ([\d.]+)', head).group(1))
    surf = {}
    k = i + 1
    while k < len(rows):
        r = rows[k]
        if r and r[0].isdigit():
            n = int(r[0])
            name = r[1]
            rad = r[2]
            rest = [c for c in r[3:] if c != '(ASP)']
            vd = num(rest[3]) if len(rest) > 3 else None
            asp = '(ASP)' in r
            th = num(rest[0]) if rest else None
            mat = rest[1] if len(rest) > 1 else ''
            idx = num(rest[2]) if len(rest) > 2 else None
            surf[n] = dict(name=name, R=None if rad in ('Plano', 'Infinity') else float(rad.replace('E', 'e')),
                           t=th, mat=mat, n=idx, vd=vd, asp=asp, k=0.0, A={})
            if name == 'Image':
                break
        k += 1
    # aspheric blocks follow: a header row of surface numbers, then "k =", "A4 =" ... rows
    cols = None
    while k < len(rows):
        r = [c for c in rows[k] if c != '']
        if r and all(c.isdigit() for c in r):
            cols = [int(c) for c in r]
        elif r and cols and r[0].endswith('='):
            key = r[0].rstrip(' =')
            for s, v in zip(cols, r[1:]):
                x = num(v)
                if x is None:
                    continue
                if key == 'k':
                    surf[s]['k'] = x
                else:
                    surf[s]['A'][int(key[1:])] = x
        elif r and any('Embodiment' in c for c in r):
            break
        k += 1
    return dict(f=f, fno=fno, hfov=hfov, surf=[surf[n] for n in sorted(surf)])


class Lens:
    def __init__(self, d):
        self.d = d
        z = 0.0
        self.S = []
        n_before = 1.0
        for s in d['surf'][1:]:  # skip object
            n_after = s['n'] if s['n'] and s['mat'] not in ('', '—') else 1.0
            self.S.append(dict(s, z=z, n1=n_before, n2=n_after))
            n_before = n_after
            if s['t'] is not None:
                z += s['t']
        self.ttl = self.S[-1]['z'] - self.S[0]['z']
        self.stop = next(j for j, s in enumerate(self.S) if 'Stop' in s['name'])

    @staticmethod
    def sag(s, y):
        z = 0.0
        if s['R']:
            c = 1.0 / s['R']
            z += c * y * y / (1 + math.sqrt(max(0.0, 1 - (1 + s['k']) * c * c * y * y)))
        for i, a in s['A'].items():
            z += a * y ** i
        return z

    @staticmethod
    def dsag(s, y):
        d = 0.0
        if s['R']:
            c = 1.0 / s['R']
            d += c * y / math.sqrt(max(1e-12, 1 - (1 + s['k']) * c * c * y * y))
        for i, a in s['A'].items():
            d += i * a * y ** (i - 1)
        return d

    def trace(self, y0, theta, upto=None):
        """Ray through (z=0, y=y0) at angle theta (rad). Returns list of (z, y) hit points; None on failure."""
        P = np.array([-1.0, y0 - math.tan(theta)])
        D = np.array([math.cos(theta), math.sin(theta)])
        pts = [P.copy()]
        for j, s in enumerate(self.S if upto is None else self.S[:upto + 1]):
            t = (s['z'] - P[0]) / D[0]
            for _ in range(50):  # Newton on z(t) - surface(y(t))
                y = P[1] + t * D[1]
                g = P[0] + t * D[0] - s['z'] - self.sag(s, y)
                dg = D[0] - self.dsag(s, y) * D[1]
                step = g / dg
                t -= step
                if abs(step) < 1e-12:
                    break
            P = P + t * D
            pts.append(P.copy())
            if s['n1'] != s['n2']:
                nrm = np.array([1.0, -self.dsag(s, P[1])])
                nrm /= np.linalg.norm(nrm)
                ci = nrm @ D
                if ci < 0:
                    nrm, ci = -nrm, -ci
                mu = s['n1'] / s['n2']
                kk = 1 - mu * mu * (1 - ci * ci)
                if kk < 0:
                    return None
                D = mu * D + (math.sqrt(kk) - mu * ci) * nrm
                D /= np.linalg.norm(D)
        return pts, D

    def aim(self, theta, y_stop):
        """Find y0 so that the ray crosses the stop plane at height y_stop (secant)."""
        def g(y0):
            r = self.trace(y0, theta, upto=self.stop)
            return r[0][-1][1] - y_stop
        a, b = -1.0, 1.0
        ga, gb = g(a), g(b)
        for _ in range(60):
            c = b - gb * (b - a) / (gb - ga)
            a, ga, b, gb = b, gb, c, g(c)
            if abs(gb) < 1e-10:
                break
        return b


def main():
    html = sys.argv[1]
    emb = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out = sys.argv[3] if len(sys.argv) > 3 else None
    d = parse(html, emb)
    L = Lens(d)
    # paraxial EFL from a near-axis parallel ray
    h = 1e-4
    pts, D = L.trace(h, 0.0)
    efl = -h / (D[1] / D[0])
    epr = d['f'] / d['fno'] / 2
    r_stop = L.trace(epr, 0.0, upto=L.stop)[0][-1][1]
    th = math.radians(d['hfov'])
    yc = L.aim(th, 0.0)
    img_h = L.trace(yc, th)[0][-1][1]
    print(f"patent: f={d['f']} Fno={d['fno']} HFOV={d['hfov']}  surfaces={len(L.S)}")
    print(f"trace : EFL={efl:.3f} mm  TTL(surface1→image)={L.ttl:.3f} mm  TTL/f={L.ttl/efl:.2f}  "
          f"stop radius={r_stop:.3f} mm  chief-ray image height at HFOV={abs(img_h):.3f} mm "
          f"(f·tanθ={d['f']*math.tan(th):.3f})")
    eq = 21.633 / math.tan(th)
    print(f"        35mm-equivalent focal length ≈ {eq:.1f} mm, image circle diagonal ≈ {2*abs(img_h):.2f} mm")
    lenses = sum(1 for s in L.S if s['name'].startswith('Len'))
    print(f"        lens elements: {lenses}")
    # spot check at the image plane
    for frac in (0.0, 0.7, 1.0):
        t = math.atan(frac * math.tan(th))
        ys = []
        for p in np.linspace(-1, 1, 11):
            y0 = L.aim(t, p * r_stop)
            r = L.trace(y0, t)
            if r:
                ys.append(r[0][-1][1])
        ys = np.array(ys)
        print(f"        field {frac:.1f}: image y = {ys.mean():+.4f} mm, meridional spread = {1000*(ys.max()-ys.min()):.1f} µm")
    if out:
        draw(L, d, r_stop, th, out)
        export(L, d, r_stop, th, out.rsplit('.', 1)[0] + '.json')


def cauchy(nd, vd):
    """n(lambda) from nd and Abbe number (Cauchy fit through nF - nC = (nd - 1)/vd); lambda in micrometres."""
    if not vd:
        return lambda lam: nd
    lf, lc, ld = 0.4861, 0.6563, 0.5876
    B = (nd - 1) / vd / (1 / lf ** 2 - 1 / lc ** 2)
    A = nd - B / ld ** 2
    return lambda lam: A + B / lam ** 2


def ray_set(L, r_stop, th, fracs=(-1.0, -0.7, -0.35, 0.0, 0.35, 0.7, 1.0), pupil=15):
    """Meridional fans for several fields; the stop crossing is dropped from the polyline (the stop sits inside the
    sag of the next surface, so the sequential trace runs a short way back there)."""
    out, maxy = [], [0.0] * len(L.S)
    for frac in fracs:
        t = math.atan(frac * math.tan(th))
        for p in np.linspace(-1, 1, pupil):
            y0 = L.aim(t, p * r_stop)
            r = L.trace(y0, t)
            if not r:
                continue
            pts = [q for j, q in enumerate(r[0]) if j == 0 or j - 1 != L.stop]
            for j in range(len(L.S)):
                if j != L.stop:
                    maxy[j] = max(maxy[j], abs(r[0][j + 1][1]))
            out.append(dict(field=frac, pupil=float(p), pts=[[float(a), float(b)] for a, b in pts]))
    return out, maxy


def export(L, d, r_stop, th, path):
    import json
    rays, maxy = ray_set(L, r_stop, th)
    els = []
    for j, s in enumerate(L.S[:-1]):
        if s['n2'] > 1.0:
            b = L.S[j + 1]
            els.append(dict(name=s['name'], material=s['mat'], nd=s['n'],
                            front=dict(z=s['z'], R=s['R'], k=s['k'], A=s['A'], ap=maxy[j] * 1.03),
                            back=dict(z=b['z'], R=b['R'], k=b['k'], A=b['A'], ap=maxy[j + 1] * 1.03)))
    vd = {s['name']: s.get('vd') for s in d['surf']}
    json.dump(dict(source='Largan US10302915B2, embodiment 1 (Google Patents full text)', f=d['f'], fno=d['fno'],
                   hfov=d['hfov'], ttl=L.ttl, stop_z=L.S[L.stop]['z'], stop_r=r_stop, image_z=L.S[-1]['z'],
                   elements=els, rays=rays), open(path, 'w'), indent=1)
    print('saved', path, len(els), 'elements,', len(rays), 'rays')


def draw(L, d, r_stop, th, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cols = {0.0: '#4da3ff', 0.7: '#5fd38d', 1.0: '#ff8a4d'}
    rs, maxy = ray_set(L, r_stop, th, fracs=(-1.0, -0.7, 0.0, 0.7, 1.0), pupil=9)
    rays = [(np.array(r['pts']), cols[abs(r['field'])]) for r in rs]
    fig, ax = plt.subplots(figsize=(12, 5), dpi=200)
    fig.patch.set_facecolor('#0d0f12')
    ax.set_facecolor('#0d0f12')
    for j, s in enumerate(L.S[:-1]):
        if s['n2'] > 1.0 and j + 1 < len(L.S):
            a, b = s, L.S[j + 1]
            ya = np.linspace(-maxy[j] * 1.02, maxy[j] * 1.02, 200)
            yb = np.linspace(-maxy[j + 1] * 1.02, maxy[j + 1] * 1.02, 200)
            za = [a['z'] + L.sag(a, y) for y in ya]
            zb = [b['z'] + L.sag(b, y) for y in yb]
            zs = za + [zb[-1]] + zb[::-1] + [za[0]]
            ys = list(ya) + [yb[-1]] + list(yb[::-1]) + [ya[0]]
            fc = '#9fb7c9' if 'Glass' not in s['mat'] else '#c9b38f'
            ax.fill(zs, ys, color=fc, alpha=0.28, lw=0)
            ax.plot(za, ya, color='#cfe3f2', lw=0.8)
            ax.plot(zb, yb, color='#cfe3f2', lw=0.8)
    for pts, col in rays:
        ax.plot(pts[1:, 0], pts[1:, 1], color=col, lw=0.45, alpha=0.9)
    zi = L.S[-1]['z']
    ax.plot([zi, zi], [-max(maxy) * 1.05, max(maxy) * 1.05], color='#ffffff', lw=1.0)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(f"Largan US10302915B2, 1st embodiment — f {d['f']} mm, f/{d['fno']}, HFOV {d['hfov']}°, "
                 f"TTL {L.ttl:.2f} mm (our trace)", color='#cfd6dd', fontsize=9)
    fig.savefig(out, bbox_inches='tight', facecolor=fig.get_facecolor())
    print('saved', out)


if __name__ == '__main__':
    main()
