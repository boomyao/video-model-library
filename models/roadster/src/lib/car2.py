# Roadster stunt car, v3 body.
# Wedge nose: the hood sweeps down to a knife edge carrying the full-width light bar; the dark lower face is undercut
# below it; raised fender pods either side with triangular headlight slits running up and back from the bar's ends.
# Low glass bubble (windshield, glass roof, rear glass) on a wide body with a crisp shoulder; long flat tail with a
# full-width red light, plate, four rear nozzles on a nozzle bar and four round fan openings in the diffuser.
# Underneath: the stunt car's 5 x 4 grid frame, a flexible ground seal inboard of the sills, lift nozzles behind the
# wheels (fact table S65) built as real parts (bell, throat, flange, bracket, feed pipe).
# Car-local frame: origin on the road at mid-wheelbase, +X forward, +Y left, +Z up.
# Shapes are judged from Tesla's 4K stills and the stunt-car frames of The Ramp / The Kickflip (reference only).
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
import lib_rog as L

WB = 2.80
AX_F, AX_R = WB / 2, -WB / 2
TRACK_Y = 0.835
R_WHEEL = 0.32
W_TIRE = 0.29
R_ARCH = 0.355
ARCH_DZ = 0.04        # arch centre sits above the axle: 7.5 cm over the tyre at rest, still clear with a 6.5 cm squash
X_TAIL, X_FRONT = -2.22, 2.20
GAP = 0.0028          # half of a panel gap (shut lines ~5-6 mm)

X_DOOR_F, X_DOOR_R = 0.74, -0.60   # door shut lines
X_WS = 1.19           # windshield base / A-pillar base (AP)
X_CAN_R = -0.60       # canopy | rear glass split on the roof
X_GTIP = -1.10        # rear tip of the side glass (behind it the quarter's top rises to the roof rail)
X_RG = -1.95          # rear glass meets the deck
X_LE = 1.66           # main loft (and the fender) ends here; the nose fascia (pods, lower face) is built from patches
X_TT = -2.20          # main loft ends at the tail's top edge
# Nose (v4, after the film review: "rounded drooping nose, C-shaped light bar"): in plan the light bar is a straight,
# shallow V (centre forward, straight halves) ending in crisp corners K; from each K the pod's front face runs back
# as a flat chamfer (~35 deg to the car's axis) to a tight vertical corner J in front of the wheel arch, where it
# turns into the side (m013 plan, m066 / z025 front: straight bar, flat angled pod faces). The hood is a straight
# wedge from the windshield base down to the knife edge; the dark lower face is undercut ~25 deg below it.
K_CORNER = (2.13, 0.700, 0.478)    # light bar end: knife edge, hood seam and the pod's brow meet here
T_TIP = (2.20, 0.0, 0.478)         # centre of the knife edge (the bar is level: a V in plan only)
KNIFE_W = 0.12                     # rounding of the V's point (plan), m
PB_IN = (2.080, 0.735, 0.250)      # bottom of a pod's inner front edge (the edge stands nearly vertical under K)
LF_X = 2.095                       # bottom edge of the lower face at the centre (undercut ~10.5 cm below the tip)
J_TOP = (1.750, 0.968, 0.735)      # the pod's vertical corner (side -> chamfer) at the brow ...
J_BOT = (1.790, 0.952, 0.274)      # ... and at the bottom
R_J = 0.030                        # rounding of that corner (plan)
X_SLB = 1.95          # headlight slit: rear end on the hood seam (B) ...
X_SLC = 1.82          # ... and on the brow (C). The slit is the triangle K-B-C, its LEDs along B-C.
Z_FOLD, Z_SPLIT, U_TAIL = 0.770, 0.550, 0.075   # tail: undercut fold, panel/diffuser split, undercut depth


# ------------------------------------------------------------------ design lines (left side)
LINE_SIGMA = 0.035    # design lines: PCHIP through the knots, then a light Gaussian blur along x (sigma, m)


def _mk(knots, sigma=None):
    """Design line through (x, value) knots. PCHIP keeps it from overshooting between knots but is only C1: its
    curvature jumps at every knot, which shows as kinks in the paint's highlights. A Gaussian blur along x (end
    values kept exactly by point-mirroring the curve about its ends) makes the curvature continuous."""
    xs = np.array([k[0] for k in knots], float)
    vs = np.array([k[1] for k in knots], float)
    sigma = LINE_SIGMA if sigma is None else sigma
    step = 0.002
    grid = np.linspace(xs[0], xs[-1], max(2, int(round((xs[-1] - xs[0]) / step)) + 1))
    vals = np.asarray(L.pchip(xs, vs, grid), float)
    npad = int(4 * sigma / step) if sigma > 0 else 0
    if 0 < npad < len(vals) - 1:
        ext = np.concatenate([2 * vals[0] - vals[1:npad + 1][::-1], vals, 2 * vals[-1] - vals[-npad - 1:-1][::-1]])
        kx = np.arange(-npad, npad + 1) * step
        w = np.exp(-0.5 * (kx / sigma) ** 2)
        vals = np.convolve(ext, w / w.sum(), mode='valid')

    def f(x):
        return float(np.interp(float(x), grid, vals))
    return f


KN = {
    'flz': [(-2.22, 0.175), (1.00, 0.175), (1.45, 0.185), (1.75, 0.215)],
    'fly': [(-2.22, 0.780), (-2.00, 0.830), (-1.70, 0.860), (1.45, 0.860), (1.75, 0.815)],
    'sby': [(-2.22, 0.840), (-2.00, 0.895), (-1.70, 0.925), (1.45, 0.925), (1.75, 0.905)],
    'sbz': [(-2.22, 0.235), (-1.95, 0.212), (-1.60, 0.195), (1.30, 0.195), (1.75, 0.235)],
    'lcy': [(-2.22, 0.865), (-2.05, 0.925), (-1.80, 0.958), (-1.40, 0.968), (0.00, 0.966), (1.40, 0.968),
            (1.75, 0.958)],
    'lcz': [(-2.22, 0.500), (-1.95, 0.485), (-1.40, 0.455), (-0.95, 0.430), (-0.30, 0.385), (0.30, 0.345),
            (0.74, 0.318), (1.30, 0.300), (1.75, 0.290)],
    # shoulder crease; in front of the loft it is the pod's brow (brow(), with the corner J): over the slit's outer
    # lip down to the light bar end. The knots past X_LE only steer the loft's end tangent.
    'scy': [(-2.20, 0.878), (-2.08, 0.935), (-1.92, 0.978), (-1.65, 0.997), (-1.40, 1.000), (-1.10, 0.995),
            (-0.60, 0.983), (0.00, 0.976), (0.60, 0.978), (1.00, 0.986), (1.40, 0.990), (1.56, 0.987),
            (1.66, 0.981), (1.75, 0.968), (1.85, 0.897), (1.95, 0.827), (2.05, 0.756), (2.13, 0.700)],
    'scz': [(-2.20, 0.850), (-1.95, 0.856), (-1.60, 0.848), (-1.30, 0.836), (-1.00, 0.818), (-0.50, 0.796),
            (0.00, 0.785), (0.60, 0.780), (1.00, 0.782), (1.25, 0.785), (1.45, 0.785), (1.58, 0.778),
            (1.66, 0.764), (1.75, 0.735), (1.85, 0.667), (1.95, 0.600), (2.05, 0.532), (2.13, 0.478)],
    # waist crease on the white side: from behind the front wheel it rises over the rear wheel and runs to the tail
    # (m072's hard line); crease height (z) of the side profile
    'crz': [(-2.22, 0.735), (-1.80, 0.748), (-1.40, 0.750), (-1.00, 0.722), (-0.40, 0.680), (0.40, 0.628),
            (1.00, 0.588), (1.40, 0.566), (1.66, 0.555)],
    'scr': [(-2.20, 0.020), (-1.85, 0.040), (-1.40, 0.045), (-1.00, 0.028), (-0.50, 0.012), (0.60, 0.012),
            (1.00, 0.022), (1.30, 0.028), (1.50, 0.020), (1.66, 0.010)],
    'wly': [(-1.10, 0.520), (-0.90, 0.700), (-0.60, 0.830), (0.00, 0.872), (0.74, 0.862), (1.00, 0.815),
            (1.19, 0.745)],
    'wlz': [(-1.10, 1.015), (-0.90, 0.925), (-0.60, 0.835), (0.00, 0.795), (0.74, 0.785), (1.00, 0.780),
            (1.19, 0.780)],
    'rry': [(-2.20, 0.282), (-1.95, 0.300), (-1.65, 0.385), (-1.30, 0.462), (-0.90, 0.528), (-0.50, 0.563),
            (0.00, 0.577), (0.45, 0.597), (0.75, 0.655), (1.00, 0.708), (1.19, 0.745)],
    'rrz': [(-2.20, 0.905), (-1.95, 0.925), (-1.65, 0.958), (-1.30, 0.995), (-0.90, 1.038), (-0.50, 1.068),
            (0.00, 1.080), (0.45, 1.066), (0.75, 0.993), (1.00, 0.885), (1.19, 0.780)],
    'topz': [(-2.20, 0.905), (-1.95, 0.932), (-1.60, 0.970), (-1.20, 1.018), (-0.80, 1.060), (-0.40, 1.090),
            (-0.10, 1.100), (0.20, 1.097), (0.45, 1.080), (0.75, 1.000), (1.00, 0.893), (1.19, 0.785)],
    # hood seam and hood centre line: a straight wedge (17 deg) from the windshield base to the knife edge, the hood
    # sunk between the raised pods
    'smy': [(1.19, 0.745), (1.40, 0.747), (1.60, 0.741), (1.80, 0.729), (2.00, 0.713), (2.13, 0.700)],
    'smz': [(1.19, 0.780), (1.30, 0.759), (1.40, 0.731), (1.60, 0.664), (1.80, 0.598), (2.00, 0.533), (2.13, 0.478)],
    'hcz': [(1.19, 0.785), (1.30, 0.766), (1.40, 0.740), (1.60, 0.674), (1.80, 0.609), (2.00, 0.544), (2.20, 0.478)],
}
LINE_SIGMA_K = {'rry': 0.08, 'rrz': 0.08, 'topz': 0.08}   # the glass bubble's lines: sparse knots, wider blur
LN = {k: _mk(v, LINE_SIGMA_K.get(k)) for k, v in KN.items()}


def ln(name, x):
    return LN[name](x)


def seam(x):
    """Hood/fender seam (left), x in [X_WS, K_CORNER.x]."""
    return np.array([x, ln('smy', x), ln('smz', x)])


def _round_corner(P0, P1, P2, d, n_arc=8):
    """Straight P0 -> P1 -> P2 with the corner at P1 replaced by a quadratic Bezier from C1 (d before P1) to C2 (d
    after). Returns (C1, arc points C1..C2 (n_arc + 1), C2)."""
    P0, P1, P2 = (np.asarray(v, float) for v in (P0, P1, P2))
    C1 = P1 + (P0 - P1) / np.linalg.norm(P0 - P1) * d
    C2 = P1 + (P2 - P1) / np.linalg.norm(P2 - P1) * d
    arc = np.array([(1 - t) ** 2 * C1 + 2 * (1 - t) * t * P1 + t * t * C2 for t in np.linspace(0, 1, n_arc + 1)])
    return C1, arc, C2


D_J = 0.020           # tangent length of the rounded corner J (the corner zone is ~4 cm wide)
_BROW_NOSE = []


def _brow_nose():
    """Brow in front of the loft as a dense polyline (x increasing): straight from the loft end to the corner J_TOP
    (rounded), then the straight chamfer edge down to the light bar end K."""
    if not _BROW_NOSE:
        P0 = np.array([X_LE, ln('scy', X_LE), ln('scz', X_LE)])
        C1, arc, C2 = _round_corner(P0, J_TOP, K_CORNER, D_J)
        a = np.array([P0 + (C1 - P0) * t for t in np.linspace(0, 1, 24)])
        b = np.array([C2 + (np.array(K_CORNER) - C2) * t for t in np.linspace(0, 1, 80)])
        _BROW_NOSE.append(np.vstack([a[:-1], arc, b[1:]]))
    return _BROW_NOSE[0]


def brow(x):
    """Shoulder crease / pod brow (left), any x up to K_CORNER.x."""
    if x <= X_LE:
        return np.array([x, ln('scy', x), ln('scz', x)])
    P = _brow_nose()
    x = min(x, K_CORNER[0])
    return np.array([x, float(np.interp(x, P[:, 0], P[:, 1])), float(np.interp(x, P[:, 0], P[:, 2]))])


def fender_edge(x):
    """Inner top edge of the fender (y, z): the hood seam."""
    return seam(x)[1:]


# ------------------------------------------------------------------ profiles
NSEG = dict(A=8, B=3, C=4, U=2, D=10, R=6, E=7, F=8, G=12)
ORDER = 'ABCUDREFG'
SEGS = NSEG            # kept for older callers


def _shape(t, kind):
    if kind == 'mid':        # symmetric, slope at both ends
        return 4 * t * (1 - t)
    if kind == 'top':        # fuller toward t=1, zero slope at t=1 (joins the shoulder fillet smoothly)
        return (t ** 2) * ((1 - t) ** 2) / 0.0625 * (0.6 + 0.8 * t) / 1.0
    if kind == 'start':      # zero slope at t=0 (leaves the fillet smoothly)
        return (t ** 2) * ((1 - t) ** 2) / 0.0625 * (1.4 - 0.8 * t) / 1.0
    return 0.0


def _bulge(p0, p1, n, amount, kind='mid'):
    """Points from p0 (excluded) to p1 (included), bowed by `amount` to the right of the direction of travel
    (outward for a half profile walked from the bottom centre to the top centre)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    nrm = np.array([d[1], -d[0]])
    ln_ = np.linalg.norm(nrm)
    nrm = nrm / ln_ if ln_ > 1e-9 else nrm
    out = []
    for k in range(1, n + 1):
        t = k / n
        out.append(p0 + d * t + nrm * amount * _shape(t, kind))
    return out


CREASE_PROT = 0.028   # how far the waist crease stands out of the straight line from the lower crease to the shoulder
CREASE_YMAX = 1.006   # ... capped at this half-width (the car stays ~2.0 m wide over the rear haunches)
CREASE_UNDER = (0.013, 0.012)   # (in, down): the edge overhangs a small undercut, a shadow line under the crease


def _crease_prot(x):
    """Crease depth along the car: full from the tail to just behind the front wheel, gone over the front arch
    (it runs out of the wheel arch's rear edge), shallower at the very tail where the body tapers in."""
    front = 1.0 - min(1.0, max(0.0, (x - 1.15) / 0.25))
    tail = 0.25 + 0.75 * min(1.0, max(0.0, (x - X_TT) / 0.30))
    return CREASE_PROT * front * tail


def _side_crease(P_lc, C1, z_cr, prot, n, bU, full=0.0):
    """n side points from the lower crease P_lc (excluded) to the shoulder fillet's start C1 (included) with a waist
    crease at height z_cr standing `prot` out of the straight line from P_lc to C1. Above the crease the side leans in
    to the shoulder; at the crease a crisp, slightly rounded edge overhangs a small undercut (CREASE_UNDER, scaled
    with prot), so the line reads as a hard fold with a shadow under it in any top light; below it the side tucks in
    to the lower crease. As the crease fades (prot -> 0) the edge and the undercut keep their spacing along the side
    and only lose depth, so no rows collapse into slivers; with `full` (the plain side's bulge) the side also gets its
    plain fullness back where the crease is gone (over the front wheel), with the same rows."""
    P_lc, C1 = np.asarray(P_lc, float), np.asarray(C1, float)
    d = C1 - P_lc
    L2 = max(float(d.dot(d)), 1e-12)
    nrm = np.array([d[1], -d[0]]) / max(np.linalg.norm(d), 1e-9)
    t = min(0.85, max(0.25, (z_cr - P_lc[1]) / max(d[1], 1e-6)))
    E = P_lc + d * t + nrm * prot
    E[0] = min(E[0], max(CREASE_YMAX, P_lc[0], C1[0]))
    k = min(1.0, prot / CREASE_PROT)
    ks = k * k * (3 - 2 * k)
    sb = ks if full > 0.0 else 1.0
    U1 = E - np.array([CREASE_UNDER[0] * k, CREASE_UNDER[1]])            # bottom of the undercut
    Em = E - np.array([0.0022 * k, 0.0012])                              # rounding of the edge
    up = (C1 - E) / np.linalg.norm(C1 - E)
    E2 = E + up * 0.006
    n_up = n - 5
    pts = _bulge(P_lc, U1, 3, -0.0015 * sb, 'mid')
    pts.append(Em)
    pts.append(E2)
    pts += _bulge(E2, C1, n_up, bU * sb, 'top')
    if full > 0.0 and ks < 1.0:
        pts = [p + nrm * (full * (1.0 - ks) * _shape(min(1.0, max(0.0, float((p - P_lc).dot(d)) / L2)), 'top'))
               for p in pts]
    return pts


def _fillet(P_lc, S, P_in, r, nD, nR, nE, bD, bE, crease=None):
    """Side line LC -> corner S -> top line to P_in, the corner rounded with radius ~r.
    Returns (side points, arc points, top points), each excluding its start point. crease=(z, prot[, full]): the side
    gets the waist crease (_side_crease) instead of a plain bulge (full: the plain bulge it returns to where the crease
    fades out)."""
    P_lc, S, P_in = (np.asarray(v, float) for v in (P_lc, S, P_in))
    a = P_lc - S
    la = np.linalg.norm(a)
    b = P_in - S
    lb = np.linalg.norm(b)
    if la < 1e-6 or lb < 1e-6:
        side = _bulge(P_lc, S, nD, 0.0)
        arc = [S.copy() for _ in range(nR)]
        top = _bulge(S, P_in, nE, 0.0)
        return side, arc, top
    a /= la
    b /= lb
    th = math.acos(max(-1.0, min(1.0, float(a.dot(b)))))
    d = r / max(math.tan(th / 2), 1e-3)
    d = min(d, 0.4 * la, 0.4 * lb)
    C1 = S + a * d
    C2 = S + b * d
    if crease is not None:
        side = _side_crease(P_lc, C1, crease[0], crease[1], nD, 0.35 * bD, full=crease[2] if len(crease) > 2 else 0.0)
    else:
        side = _bulge(P_lc, C1, nD, bD, 'top')
    arc = []
    for k in range(1, nR + 1):
        t = k / nR
        arc.append((1 - t) ** 2 * C1 + 2 * (1 - t) * t * S + t * t * C2)
    top = _bulge(C2, P_in, nE, bE, 'start')
    return side, arc, top


def _rail_at(x):
    """Roof rail / A-pillar / rear glass edge (y, z); on the seam in front of the windshield."""
    if x >= X_WS:
        return seam(x)[1:]
    return np.array([ln('rry', x), ln('rrz', x)])


def _wl_at(x):
    """Bottom edge of the side glass (y, z); equals the rail behind the glass tip, the fender edge in front of AP."""
    if x >= X_WS:
        return fender_edge(x)
    if x <= X_GTIP:
        return _rail_at(x)
    w = np.array([ln('wly', x), ln('wlz', x)])
    k = min(1.0, (x - X_GTIP) / 0.12)
    k = 1.0 - (1.0 - k) ** 3        # leaves the rail at an angle (a clean glass tip), joins the belt line smoothly
    return _rail_at(x) * (1 - k) + w * k


def _top_at(x):
    if x >= X_WS:
        return ln('hcz', x)
    return ln('topz', x)


def profile_at(x):
    """Half profile (bottom centre -> top centre) at station x: list of (y, z) and per-point segment tags.
    In front of the loft (the nose) it returns a simplified section of the nose (used by the air effect)."""
    if x > X_LE:
        return _nose_profile(x)
    x = max(x, X_TT)
    flz = ln('flz', x)
    fl = np.array([ln('fly', x), flz])
    sb = np.array([ln('sby', x), ln('sbz', x)])
    lc = np.array([ln('lcy', x), ln('lcz', x)])
    st = np.array([lc[0] - 0.030, lc[1] - 0.018])
    sc = np.array([ln('scy', x), ln('scz', x)])
    wl = _wl_at(x)
    rr = _rail_at(x)
    zt = _top_at(x)
    pts, tags = [np.array([0.0, flz])], ['A']
    for k in range(1, NSEG['A'] + 1):
        pts.append(np.array([fl[0] * k / NSEG['A'], flz]))
        tags.append('A')
    for p in _bulge(fl, sb, NSEG['B'], 0.010):
        pts.append(p); tags.append('B')
    for p in _bulge(sb, st, NSEG['C'], 0.004):
        pts.append(p); tags.append('C')
    for p in _bulge(st, lc, NSEG['U'], 0.0):
        pts.append(p); tags.append('U')
    tb = min(1.0, max(0.0, (x - 0.50) / 0.45))
    bD = 0.016 + 0.004 * tb * tb * (3 - 2 * tb)          # fuller side over the front wheel, no step at the shut line
    side, arc, top = _fillet(lc, sc, wl, ln('scr', x), NSEG['D'], NSEG['R'], NSEG['E'], bD, 0.006,
                             crease=(ln('crz', x), _crease_prot(x), bD if x > 1.0 else 0.0))
    for p in side:
        pts.append(p); tags.append('D')
    for p in arc:
        pts.append(p); tags.append('R')
    for p in top:
        pts.append(p); tags.append('E')
    for p in _bulge(wl, rr, NSEG['F'], 0.006 if x < X_WS else 0.0):
        pts.append(p); tags.append('F')
    nG = NSEG['G']
    for k in range(1, nG + 1):
        t = k / nG
        y = rr[0] * (1 - t)
        z = zt + (rr[1] - zt) * (y / rr[0]) ** 2 if rr[0] > 1e-6 else zt
        pts.append(np.array([y, z])); tags.append('G')
    return pts, tags


# ------------------------------------------------------------------ loft
def station_xs():
    xs = set()
    for a, b, n in ((X_TT, X_RG, 14), (X_RG, -1.80, 8), (-1.80, X_GTIP, 14), (X_GTIP, -1.0, 34),
                    (-1.0, X_DOOR_R, 24), (X_DOOR_R, 0.0, 40), (0.0, X_DOOR_F, 48), (X_DOOR_F, 1.00, 18),
                    (1.00, X_WS, 14), (X_WS, 1.40, 16), (1.40, X_LE, 28)):
        for v in np.linspace(a, b, n + 1):
            xs.add(round(float(v), 5))
    return sorted(xs)


def _tail_u(z):
    """Undercut depth of the tail panel at height z (planar pieces: vertical above the fold, tilted to the split,
    vertical below)."""
    if z >= Z_FOLD:
        return 0.0
    if z >= Z_SPLIT:
        return U_TAIL * (Z_FOLD - z) / (Z_FOLD - Z_SPLIT)
    return U_TAIL


def _tail_shift(x, z):
    """Undercut of the tail below the light band: the lower tail recedes (applied near the rear end only)."""
    if x > -2.02:
        return 0.0
    s = min(1.0, max(0.0, (-2.02 - x) / (-2.02 - X_TT)))
    s = s * s * (3 - 2 * s)
    return _tail_u(z) * s


def loft_grid():
    xs = station_xs()
    rings, tags = [], None
    for x in xs:
        half, tg = profile_at(x)
        tags = tg
        rings.append((x, half))
    nh = len(rings[0][1])
    P = np.zeros((len(xs), 2 * nh - 2, 3))
    T, S = [], []
    for j in range(nh):
        T.append(tags[j]); S.append(1)
    for j in range(nh - 2, 0, -1):
        T.append(tags[j]); S.append(-1)
    for i, (x, half) in enumerate(rings):
        for j in range(nh):
            P[i, j] = (x, half[j][0], half[j][1])
        for k, j in enumerate(range(nh - 2, 0, -1)):
            P[i, nh + k] = (x, -half[j][0], half[j][1])
    for i in range(len(xs)):
        for j in range(P.shape[1]):
            P[i, j, 0] += _tail_shift(P[i, j, 0], P[i, j, 2])
    return xs, P, T, S, nh


def _face_seg(T, j, m):
    a, b = T[j], T[(j + 1) % m]
    return a if ORDER.index(a) > ORDER.index(b) else b


def _panel_of(xc, seg, side):
    s = 'L' if side > 0 else 'R'
    if seg in ('A', 'B'):
        return 'floor'
    if seg == 'C':
        return 'sill_' + s
    if seg in ('U', 'D', 'R', 'E'):
        if xc > X_DOOR_F:
            return 'fender_' + s
        if xc > X_DOOR_R:
            return 'door_' + s
        return 'quarter_' + s
    if seg == 'F':
        if xc > X_WS:
            return None
        if xc > X_GTIP:
            # the first few millimetres of the glass's tip stay open (a sliver would only overlap its neighbours)
            return 'canopy' if np.linalg.norm(_wl_at(xc) - _rail_at(xc)) > 0.006 else None
        return None
    if xc > X_WS:
        return None
    if xc > X_CAN_R:
        return 'canopy'
    if xc > X_RG:
        return 'rearglass'
    return 'deck'


def _crease_cols(m):
    """Profile columns that are sharp edges along x."""
    j = 0
    idx = {}
    for s in ORDER:
        idx[s] = j
        j += NSEG[s]
    cols = set()
    for s in ('C', 'U', 'D', 'F', 'G'):
        jj = idx[s]          # first point of the segment's span is the end of the previous segment
        cols.add(jj)
        cols.add(m - jj)
    return cols


X_CREASE_SHARP = 1.27  # the waist crease's edges are sharp (crisp shading) where it is at least half depth


def _waist_cols(m):
    """Profile columns of the waist crease: the undercut's bottom and the edge (_side_crease points 3 and 4 of D)."""
    j = 0
    for s in ORDER:
        if s == 'D':
            break
        j += NSEG[s]
    return {j + 3, j + 4, m - (j + 3), m - (j + 4)}


def build_panels(col, mats, bevel=True):
    xs, P, T, S, nh = loft_grid()
    ni, m = P.shape[0], P.shape[1]
    face_panel = {}
    for i in range(ni - 1):
        xc = 0.5 * (xs[i] + xs[i + 1])
        for j in range(m):
            jn = (j + 1) % m
            q = (P[i, j], P[i + 1, j], P[i + 1, jn], P[i, jn])
            area = np.linalg.norm(np.cross(q[2] - q[0], q[3] - q[1]))
            if area < 1e-8:
                continue
            seg = _face_seg(T, j, m)
            yc = 0.25 * (q[0][1] + q[1][1] + q[2][1] + q[3][1])
            side = 1 if yc >= 0 else -1
            pn = _panel_of(xc, seg, side)
            if pn is not None:
                face_panel[(i, j)] = pn
    crease_j = _crease_cols(m)
    waist_j = _waist_cols(m)
    panels = {}
    for nm in sorted(set(face_panel.values())):
        cells = [(i, j) for (i, j), p in face_panel.items() if p == nm]
        panels[nm] = _panel_mesh(nm, cells, P, crease_j, col, waist_j=waist_j)
    return panels, (xs, P, T, S, nh)


def _panel_mesh(nm, cells, P, crease_j, col, name=None, waist_j=()):
    ni, m = P.shape[0], P.shape[1]
    cellset = set(cells)
    used = {}
    verts = []
    for (i, j) in cells:
        for (a, b) in ((i, j), (i, (j + 1) % m), (i + 1, j), (i + 1, (j + 1) % m)):
            if (a, b) not in used:
                used[(a, b)] = len(verts)
                verts.append(P[a, b].copy())
    verts = np.array(verts)
    newv = verts.copy()
    for (a, b), vid in used.items():
        nb = []
        border = False
        for (da, db) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            aa, bb = a + da, (b + db) % m
            if da != 0:
                c1 = (min(a, aa), b)
                c2 = (min(a, aa), (b - 1) % m)
            else:
                lo = b if db == 1 else (b - 1) % m
                c1 = (a, lo)
                c2 = (a - 1, lo)
            in1, in2 = c1 in cellset, c2 in cellset
            if in1 or in2:
                if in1 != in2:
                    border = True
                nb.append((aa, bb))
        if not border:
            continue
        acc = np.zeros(3)
        cnt = 0
        for (aa, bb) in nb:
            if (aa, bb) in used and 0 <= aa < ni:
                dv = P[aa, bb] - P[a, b]
                if np.linalg.norm(dv) > 1e-6:
                    acc += dv / np.linalg.norm(dv)
                    cnt += 1
        if cnt:
            d = acc / cnt
            l_ = np.linalg.norm(d)
            if l_ > 1e-9:
                newv[vid] = verts[vid] + d / l_ * GAP
    faces = []
    for (i, j) in cells:
        jn = (j + 1) % m
        faces.append((used[(i, j)], used[(i + 1, j)], used[(i + 1, jn)], used[(i, jn)]))
    me = bpy.data.meshes.new('RS2_' + (name or nm))
    me.from_pydata([tuple(v) for v in newv], [], faces)
    me.validate()
    inv = {vid: key for key, vid in used.items()}
    sharp = []
    me.update()
    for e in me.edges:
        a, b = inv[e.vertices[0]], inv[e.vertices[1]]
        sharp.append(bool(a[1] == b[1] and (a[1] in crease_j or
                                            (a[1] in waist_j and P[a[0], a[1], 0] < X_CREASE_SHARP))))
    attr = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    attr.data.foreach_set('value', sharp)
    me.shade_smooth()
    ob = bpy.data.objects.new('RS2_' + (name or nm), me)
    col.objects.link(ob)
    return ob


# ------------------------------------------------------------------ patch helpers
def _resample(poly, n):
    Pp = np.asarray(poly, float)
    seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] < 1e-9:
        return np.repeat(Pp[:1], n, axis=0)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, Pp[:, k]) for k in range(3)], 1)


def _spline_resample(poly, n, dense=360):
    """Smooth curve through the polyline's points (C2 cubic spline over chord length, not-a-knot ends), resampled to
    n points evenly spaced along it. Used where a patch border follows a loft ring: plain linear resampling keeps the
    ring's corners, and the Coons patch would carry them inside as faint ridges (sawtooth zebra lines)."""
    P = [np.asarray(poly[0], float)]
    for q in poly[1:]:
        q = np.asarray(q, float)
        if np.linalg.norm(q - P[-1]) > 1e-7:
            P.append(q)
    P = np.array(P)
    m = len(P)
    if m < 4:
        return _resample(P, n)
    t = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    h = np.diff(t)
    A = np.zeros((m, m))
    R = np.zeros((m, 3))
    A[0, 0], A[0, 1], A[0, 2] = h[1], -(h[0] + h[1]), h[0]                     # not-a-knot at both ends
    A[-1, -3], A[-1, -2], A[-1, -1] = h[-1], -(h[-2] + h[-1]), h[-2]
    for i in range(1, m - 1):
        A[i, i - 1], A[i, i], A[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        R[i] = 6 * ((P[i + 1] - P[i]) / h[i] - (P[i] - P[i - 1]) / h[i - 1])
    M = np.linalg.solve(A, R)
    ts = np.linspace(0, t[-1], dense)
    k = np.clip(np.searchsorted(t, ts, side='right') - 1, 0, m - 2)
    hk = h[k][:, None]
    a = (t[k + 1][:, None] - ts[:, None])
    b = (ts[:, None] - t[k][:, None])
    out = (M[k] * a ** 3 + M[k + 1] * b ** 3) / (6 * hk) + (P[k] / hk - M[k] * hk / 6) * a \
        + (P[k + 1] / hk - M[k + 1] * hk / 6) * b
    out[0], out[-1] = P[0], P[-1]
    return _resample(out, n)


def _bez(p0, p1, p2, n, p3=None):
    p0, p1, p2 = (np.asarray(v, float) for v in (p0, p1, p2))
    out = []
    for k in range(n):
        t = k / (n - 1)
        if p3 is None:
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2)
        else:
            p3a = np.asarray(p3, float)
            out.append((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3a)
    return np.array(out)


def coons(c0, c1, d0, d1):
    """c0, c1: (nu,3) boundary curves at v=0 / v=1; d0, d1: (nv,3) at u=0 / u=1 (corners must match)."""
    c0, c1, d0, d1 = (np.asarray(a, float) for a in (c0, c1, d0, d1))
    nu, nv = len(c0), len(d0)
    u = np.linspace(0, 1, nu)[:, None, None]
    v = np.linspace(0, 1, nv)[None, :, None]
    P00, P10, P01, P11 = c0[0], c0[-1], c1[0], c1[-1]
    S = ((1 - v) * c0[:, None, :] + v * c1[:, None, :] + (1 - u) * d0[None, :, :] + u * d1[None, :, :]
         - ((1 - u) * (1 - v) * P00 + u * (1 - v) * P10 + (1 - u) * v * P01 + u * v * P11))
    return S


def grid_normals(S):
    du = np.gradient(S, axis=0)
    dv = np.gradient(S, axis=1)
    n = np.cross(du, dv)
    return n / (np.linalg.norm(n, axis=2, keepdims=True) + 1e-12)


def add_bulge(S, amount, pu=1.0, pv=1.0, sign=1.0):
    nu, nv = S.shape[0], S.shape[1]
    u = np.linspace(0, 1, nu)[:, None]
    v = np.linspace(0, 1, nv)[None, :]
    b = amount * (np.sin(np.pi * u) ** pu) * (np.sin(np.pi * v) ** pv)
    return S + grid_normals(S) * (b * sign)[:, :, None]


def shrink_grid(S, gap=GAP, sides=(True, True, True, True)):
    """Pull the grid's border rows/columns in along the surface by `gap` (sides: u0, u1, v0, v1)."""
    S = S.copy()
    nu, nv = S.shape[0], S.shape[1]
    orig = S.copy()
    def mv(i, j, ii, jj):
        d = orig[ii, jj] - orig[i, j]
        l_ = np.linalg.norm(d)
        if l_ > 1e-9:
            S[i, j] = S[i, j] + d / l_ * min(gap, 0.45 * l_)
    if sides[0]:
        for j in range(nv):
            mv(0, j, 1, j)
    if sides[1]:
        for j in range(nv):
            mv(nu - 1, j, nu - 2, j)
    if sides[2]:
        for i in range(nu):
            mv(i, 0, i, 1)
    if sides[3]:
        for i in range(nu):
            mv(i, nv - 1, i, nv - 2)
    return S


def grid_bm(bm, S, flip=False, mat_index=0, smooth=True):
    nu, nv = S.shape[0], S.shape[1]
    vs = [[bm.verts.new(tuple(S[i, j])) for j in range(nv)] for i in range(nu)]
    faces = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            q = (vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1])
            if flip:
                q = q[::-1]
            try:
                f = bm.faces.new(q)
            except ValueError:
                continue
            f.material_index = mat_index
            f.smooth = smooth
            faces.append(f)
    return vs, faces


def mirror_grid(S):
    M = S.copy()
    M[..., 1] *= -1
    return M


def mesh_from_grids(name, grids, col, mats=None, sharp_angle=None):
    """grids: list of (S, flip, mat_index). Builds one object."""
    bm = bmesh.new()
    for (S, flip, mi) in grids:
        grid_bm(bm, S, flip=flip, mat_index=mi)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    ob = L.bm_obj(name, bm, col, smooth=True, mat=mats)
    if sharp_angle is not None:
        ob.data.set_sharp_from_angle(angle=math.radians(sharp_angle))
    return ob


# ------------------------------------------------------------------ nose: hood, pods, lower face, slits, light bar
# The shoulder crease runs forward over the front wheel and drops over the pod as its brow; the brow is the outer lip
# of the headlight slit and ends at K, where the light bar (on the hood's knife edge) ends. Light bar + slits read as
# one V / brow graphic. The slit is the triangle K (front tip) - B (on the hood seam) - C (on the brow), its LEDs and
# reflector along the rear edge B-C. Below the brow the pod's front face wraps round the corner to the inner front
# edge K-PB; between the pods the dark lower face is undercut below the knife edge.
def knife_x(y):
    """Plan line of the knife edge: a shallow V with straight halves, its point rounded over ~KNIFE_W."""
    w, yk = KNIFE_W, K_CORNER[1]
    s = (math.sqrt(y * y + w * w) - w) / (math.sqrt(yk * yk + w * w) - w)
    return T_TIP[0] - (T_TIP[0] - K_CORNER[0]) * s


def knife_y(x):
    """Half-width of the knife edge at station x (inverse of knife_x), 0 at the tip."""
    ys = np.linspace(0.0, K_CORNER[1], 141)
    xs = np.array([knife_x(y) for y in ys])
    return float(np.interp(x, xs[::-1], ys[::-1]))


def knife_edge(n, y0=-0.70, y1=0.70):
    ys = np.linspace(y0, y1, n)
    return np.array([(knife_x(y), y, T_TIP[2] + (K_CORNER[2] - T_TIP[2]) * (y / K_CORNER[1]) ** 2) for y in ys])


def _seam_curve(n, x0=X_WS, x1=None, side=1):
    x1 = K_CORNER[0] if x1 is None else x1
    pts = []
    for x in np.linspace(x0, x1, n):
        p = seam(x)
        pts.append((p[0], side * p[1], p[2]))
    return np.array(pts)


def _poly(fn, x0, x1, n, dense=96):
    """fn(x) for x from x0 to x1, resampled to n points evenly spaced along the curve."""
    return _resample(np.array([fn(x) for x in np.linspace(x0, x1, dense)]), n)


def inner_edge(n, side=1):
    """Pod's inner front edge, from its bottom PB up to the light bar end K: a straight, near-vertical edge."""
    K, PB = np.array(K_CORNER), np.array(PB_IN)
    pts = _bez(PB, PB + (K - PB) / 3.0, K + (PB - K) / 3.0, n, K)
    return pts * np.array([1.0, side, 1.0])


def _pod_bottom_parts():
    """Pod's bottom edge in three runs: along the side from the lower crease at the loft end to the corner J_BOT,
    the rounded corner, the straight chamfer to PB. Returns (P0, C1, arc, C2, PB) (left side)."""
    P0 = np.array([X_LE, ln('lcy', X_LE), ln('lcz', X_LE)])
    C1, arc, C2 = _round_corner(P0, J_BOT, PB_IN, D_J)
    return P0, C1, arc, C2, np.array(PB_IN)


def pod_bottom(n, side=1):
    """Pod's bottom edge, from the lower crease at the loft end round the corner J_BOT to PB (n points)."""
    P0, C1, arc, C2, PB = _pod_bottom_parts()
    pts = np.vstack([np.array([P0 + (C1 - P0) * t for t in np.linspace(0, 1, 30)])[:-1], arc,
                     np.array([C2 + (PB - C2) * t for t in np.linspace(0, 1, 90)])[1:]])
    return _resample(pts, n) * np.array([1.0, side, 1.0])


def lowerface_bottom(n):
    """Bottom edge of the dark lower face (right PB -> left PB), set back under the knife edge."""
    PB = np.array(PB_IN)
    return np.array([(PB[0] + (LF_X - PB[0]) * (1 - s * s), PB[1] * s, PB[2]) for s in np.linspace(-1, 1, n)])


def _seg_index():
    idx, j = {}, 0
    for s in ORDER:
        idx[s] = (j, j + NSEG[s])
        j += NSEG[s]
    return idx


I_LC = _seg_index()['U'][1]                          # lower crease point of a profile
I_SC = _seg_index()['R'][0] + NSEG['R'] // 2         # middle of the shoulder fillet
I_R0, I_R1 = _seg_index()['R']                       # start and end of the shoulder fillet
I_WL = _seg_index()['E'][1]                          # fender edge (the hood seam in front of the windshield)
_RING_LE = []


def _ring_le():
    if not _RING_LE:
        half, _ = profile_at(X_LE)
        _RING_LE.extend(np.array([X_LE, p[0], p[1]]) for p in half)
    return _RING_LE


def _outward(S, ref):
    n = grid_normals(S)
    c = n[n.shape[0] // 2, n.shape[1] // 2]
    return 1.0 if float(np.dot(c, ref)) > 0 else -1.0


def hood_grid(nu=48, nv=48):
    """Hood: windshield base -> knife edge, between the two seams; gently crowned, lower than the pods."""
    c0 = _seam_curve(nu, side=-1)                    # right seam (v = 0)
    c1 = _seam_curve(nu, side=1)                     # left seam (v = 1)
    sp = seam(X_WS)
    zc = ln('hcz', X_WS)
    d0 = np.array([(X_WS, sp[1] * s, zc + (sp[2] - zc) * s * s) for s in np.linspace(-1, 1, nv)])
    d1 = knife_edge(nv)
    S = coons(c0, c1, d0, d1)
    return add_bulge(S, 0.006, pu=1.0, pv=0.7, sign=_outward(S, np.array([0.3, 0.0, 1.0])))


N_SIDE, N_ARC, N_BROW_LIP = 6, 2, 30   # pod samples: loft end -> corner J, corner arc intervals, slit corner C -> K
N_BROW_TOP = None                       # (older callers; the side run is now N_SIDE + N_ARC + the run to C)


def _brow_split():
    """The brow in two runs that share the slit corner C, so the pod face and the pod top meet vertex for vertex:
    loft end -> rounded corner J_TOP -> C, and C -> K. The corner sits at fixed sample indices (N_SIDE ..
    N_SIDE + N_ARC), where the pod's bottom edge puts its own corner J_BOT: one clean vertical corner line."""
    P0 = np.array([X_LE, ln('scy', X_LE), ln('scz', X_LE)])
    C1, arc, C2 = _round_corner(P0, J_TOP, K_CORNER, D_J, N_ARC)
    side = np.array([P0 + (C1 - P0) * t for t in np.linspace(0, 1, N_SIDE + 1)])
    C = brow(X_SLC)
    n_b = max(2, int(round(np.linalg.norm(C - C2) / 0.012)))
    run = np.array([C2 + (C - C2) * t for t in np.linspace(0, 1, n_b + 1)])
    a = np.vstack([side[:-1], arc, run[1:]])
    b = _poly(brow, X_SLC, K_CORNER[0], N_BROW_LIP)
    return a, b


def pod_grid(nv=30):
    """Pod front face (left): a short run of side from the loft ring at X_LE, the rounded vertical corner J, then the
    flat chamfer face forward to the inner front edge under the light bar end; top edge the brow, bottom edge the
    pod's bottom (their corners at the same sample index)."""
    ring = _ring_le()
    a, b = _brow_split()
    c1 = np.vstack([a, b[1:]])                            # shoulder -> J -> C -> K
    nu = len(c1)
    P0 = np.array([X_LE, ln('lcy', X_LE), ln('lcz', X_LE)])
    C1, arc, C2 = _round_corner(P0, J_BOT, PB_IN, D_J, N_ARC)
    side = np.array([P0 + (C1 - P0) * t for t in np.linspace(0, 1, N_SIDE + 1)])
    n_rest = nu - (N_SIDE + N_ARC + 1)
    rest = np.array([C2 + (np.array(PB_IN) - C2) * t for t in np.linspace(0, 1, n_rest + 1)])
    c0 = np.vstack([side[:-1], arc, rest[1:]])            # lower crease -> J -> PB
    d0 = _spline_resample(ring[I_LC:I_R0 + 1] + [brow(X_LE)], nv)   # lower crease -> shoulder corner, at X_LE
    d1 = inner_edge(nv)                                   # PB -> K
    S = coons(c0, c1, d0, d1)
    return add_bulge(S, 0.004, pu=0.9, pv=0.8, sign=_outward(S, np.array([0.5, 1.0, 0.0])))


def podtop_grid(nu=26):
    """Front end of the fender top (left), between the brow and the hood seam, up to the slit's rear edge C-B."""
    ring = _ring_le()
    c0 = _spline_resample([brow(X_LE)] + ring[I_R1:I_WL + 1], nu)   # shoulder corner -> seam, at X_LE
    c1 = _resample(np.array([brow(X_SLC), seam(X_SLB)]), nu)
    d0 = _brow_split()[0]                                 # the same brow vertices as the pod face's top edge
    d1 = _poly(seam, X_LE, X_SLB, len(d0))
    S = coons(c0, c1, d0, d1)
    return add_bulge(S, 0.004, sign=_outward(S, np.array([0.3, 0.2, 1.0])))


def lowerface_grid(nu=14, nv=48):
    """Dark lower face below the knife edge, undercut back to its bottom edge, between the pods' inner edges."""
    edge_L = inner_edge(nu)[::-1]                         # K -> PB
    edge_R = inner_edge(nu, side=-1)[::-1]
    S = coons(edge_R, edge_L, knife_edge(nv), lowerface_bottom(nv))
    return add_bulge(S, 0.012, pu=1.0, pv=0.5, sign=-_outward(S, np.array([1.0, 0.0, 0.0])))


def _slit_loop(side=1, n_seam=16, n_rear=9, n_brow=16):
    """Closed lip loop of a headlight slit: K -> (hood seam) -> B -> (rear edge) -> C -> (brow) -> K."""
    a = _poly(seam, K_CORNER[0], X_SLB, n_seam)
    b = _resample(np.array([seam(X_SLB), brow(X_SLC)]), n_rear)
    c = _poly(brow, X_SLC, K_CORNER[0], n_brow)
    return np.vstack([a[:-1], b[:-1], c[:-1]]) * np.array([1.0, side, 1.0]), (n_seam - 1, n_rear - 1)


def build_slits(col, mats):
    """Headlight slits: polished lips round the opening, a glowing reflector floor sunk 3 cm, the LED strip along the
    rear edge and a small projector at its inner end."""
    bm_w, bm_f, bm_l = bmesh.new(), bmesh.new(), bmesh.new()
    for s in (1, -1):
        loop, (ns, nr) = _slit_loop(side=s)
        K = np.array(K_CORNER) * [1, s, 1]
        B = seam(X_SLB) * [1, s, 1]
        Cc = brow(X_SLC) * [1, s, 1]
        nrm = np.cross(B - K, Cc - K)
        nrm /= np.linalg.norm(nrm)
        if nrm[2] > 0:
            nrm = -nrm                                     # into the body
        cen = (K + B + Cc) / 3.0
        floor = np.array([p + nrm * 0.030 + (cen - p) * 0.12 for p in loop])
        vt = [bm_w.verts.new(tuple(p)) for p in loop]
        vb = [bm_w.verts.new(tuple(p)) for p in floor]
        n = len(loop)
        for k in range(n):
            j = (k + 1) % n
            bm_w.faces.new((vt[k], vt[j], vb[j], vb[k]))
        vf = [bm_f.verts.new(tuple(p)) for p in floor]
        f = bm_f.faces.new(vf)
        bmesh.ops.triangulate(bm_f, faces=[f], quad_method='BEAUTY', ngon_method='BEAUTY')
        # LED strip on the rear wall, just above the floor
        rear = [Vector(tuple(loop[k] * 0.35 + floor[k] * 0.65)) for k in range(ns, ns + nr + 1)]
        L.bm_tube_along(bm_l, rear[1:-1], 0.0045, seg=8)
        # projector near B, looking forward along the slit
        c = Vector(tuple(loop[ns] * 0.4 + floor[ns] * 0.6)) * 0.75 + Vector(tuple(cen)) * 0.25
        d = Vector(tuple(K - (B + Cc) / 2)).normalized()
        L.bm_lathe(bm_l, [(0.0, -0.012), (0.012, -0.012), (0.013, 0.0), (0.0, 0.002)], c, d, seg=20)
    bmesh.ops.recalc_face_normals(bm_w, faces=bm_w.faces)
    walls = L.bm_obj('RS2_headglass', bm_w, col, smooth=False, mat=mats['dark_metal'])
    refl = L.bm_obj('RS2_headreflector', bm_f, col, smooth=False, mat=mats.get('reflector', mats['headlamp']))
    L.parent_keep_local(refl, walls)
    leds = L.bm_obj('RS2_headled', bm_l, col, smooth=True, mat=mats['headlamp'])
    return walls, leds


def _bottom_loop():
    """Bottom outline of the nose fascia: right loft end -> right pod -> lower face -> left pod -> left loft end."""
    return np.vstack([pod_bottom(24, side=-1), lowerface_bottom(33)[1:-1], pod_bottom(24, side=1)[::-1]])


def build_front(col, mats):
    objs = {}
    Sp = shrink_grid(pod_grid(), sides=(True, False, False, False))          # gap to the fender at X_LE
    St = shrink_grid(podtop_grid(), sides=(False, True, True, True))         # gaps to the hood, slit, fender
    Sl = lowerface_grid()
    objs['face'] = mesh_from_grids('RS2_frontface', [(Sp, True, 0), (mirror_grid(Sp), False, 0),     # all facing out
                                                       (St, False, 0), (mirror_grid(St), True, 0),
                                                       (Sl, False, 1)], col, mats=[mats['paint'], mats['gloss_black']])
    objs['face'].data.set_sharp_from_angle(angle=math.radians(32))
    # light bar on the knife edge
    bm = bmesh.new()
    ke = knife_edge(64, -0.695, 0.695)
    ke[:, 0] += 0.0015
    L.bm_tube_along(bm, [tuple(p) for p in ke], 0.0055, seg=10)
    objs['lightbar'] = L.bm_obj('RS2_lightbar', bm, col, smooth=True, mat=mats['lightbar'])
    objs['headglass'], objs['headled'] = build_slits(col, mats)
    # air dam under the pods and the lower face, undertray back to the loft's floor
    bm = bmesh.new()
    edge = [p for p in _bottom_loop() if p[0] >= 1.785]        # in front of the wheel arches
    top_v = [bm.verts.new((p[0] - 0.004, p[1], p[2] + 0.004)) for p in edge]
    bot_v = [bm.verts.new((p[0] - 0.035, p[1] * 0.985, 0.205)) for p in edge]
    for k in range(len(edge) - 1):
        bm.faces.new((top_v[k], bot_v[k], bot_v[k + 1], top_v[k + 1]))
    fv = [bm.verts.new((X_LE - 0.002 if abs(bv.co.y) < 0.60 else min(bv.co.x, 1.755), bv.co.y, 0.205))
          for bv in bot_v]
    for k in range(len(edge) - 1):
        try:
            bm.faces.new((bot_v[k], fv[k], fv[k + 1], bot_v[k + 1]))
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    objs['airdam'] = L.bm_obj('RS2_front_airdam', bm, col, mat=mats['trim'])
    # lower cap closing the loft end below the lower crease (sill and floor ends)
    half, tags = profile_at(X_LE)
    ring = [(X_LE - 0.001, p[0], p[1]) for p, t in zip(half, tags) if t in ('A', 'B', 'C', 'U')]
    ring = ring + [(x, -y, z) for (x, y, z) in ring[::-1][:-1]]
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ring]
    try:
        f = bm.faces.new(vs)
        bmesh.ops.triangulate(bm, faces=[f])
    except ValueError:
        pass
    objs['frontcap'] = L.bm_obj('RS2_front_cap', bm, col, mat=mats['trim'])
    return objs


def build_splitter(col, mats):
    """Low carbon splitter blade under the nose, its front edge following the nose outline 3-5 cm proud."""
    bm = bmesh.new()
    n = 41
    top, bot, back, backb = [], [], [], []
    kc = (PB_IN[0] - J_BOT[0]) / (J_BOT[1] - PB_IN[1])
    for s in np.linspace(-1, 1, n):
        y = 0.93 * s
        a = abs(y)
        if a <= PB_IN[1]:          # under the lower face, then along the pods' chamfered bottoms, ~4 cm proud
            xf = PB_IN[0] + (LF_X - PB_IN[0]) * (1 - (a / PB_IN[1]) ** 2) + 0.040
        else:
            xf = PB_IN[0] - (a - PB_IN[1]) * kc + 0.040
        top.append((xf, y, 0.192))
        bot.append((xf - 0.004, y, 0.170))
        back.append((1.80, y, 0.192))
        backb.append((1.80, y, 0.170))
    vt = [bm.verts.new(p) for p in top]
    vb = [bm.verts.new(p) for p in bot]
    vk = [bm.verts.new(p) for p in back]
    vkb = [bm.verts.new(p) for p in backb]
    for k in range(n - 1):
        bm.faces.new((vk[k], vt[k], vt[k + 1], vk[k + 1]))
        bm.faces.new((vb[k], vkb[k], vkb[k + 1], vb[k + 1]))
        bm.faces.new((vt[k], vb[k], vb[k + 1], vt[k + 1]))
        bm.faces.new((vkb[k], vk[k], vk[k + 1], vkb[k + 1]))
    bm.faces.new((vk[0], vkb[0], vb[0], vt[0]))
    bm.faces.new((vt[-1], vb[-1], vkb[-1], vk[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return L.bm_obj('RS2_splitter', bm, col, mat=mats['carbon_trim'] if 'carbon_trim' in mats else mats['trim'])


# ------------------------------------------------------------------ nose sections (air effect) and key-line tables
def _interp_x(curve, x):
    c = np.asarray(curve)
    o = np.argsort(c[:, 0])
    return float(np.interp(x, c[o, 0], c[o, 1])), float(np.interp(x, c[o, 0], c[o, 2]))


_POD_BOTTOM = []


def _nose_keys(x):
    """Key points (y, z) of the nose section at x > X_LE, bottom centre -> top centre."""
    if not _POD_BOTTOM:
        _POD_BOTTOM.extend(pod_bottom(64))
    zb = 0.205
    if x <= K_CORNER[0]:
        yb, zbe = _interp_x(_POD_BOTTOM, min(x, PB_IN[0]))
        sc = brow(x)
        sm = seam(x)
        zm = 0.5 * (zbe + sc[2])
        ym = 0.5 * (yb + sc[1]) + 0.018
        return [(0.0, zb), (yb * 0.97, zb), (yb, zbe), (ym, zm), (sc[1], sc[2]), (sm[1], sm[2]), (0.0, ln('hcz', x))]
    yk = max(knife_y(x), 0.002)
    q = (yk / K_CORNER[1]) ** 2
    zk = T_TIP[2] + (K_CORNER[2] - T_TIP[2]) * q
    zl = T_TIP[2] - (T_TIP[2] - PB_IN[2]) * min(1.0, max(0.0, (X_FRONT - x) / (X_FRONT - LF_X)))
    return [(0.0, zl), (yk * 0.98, zl), (yk, 0.5 * (zl + zk)), (yk, zk), (yk * 0.99, zk), (0.0, zk + 0.004)]


def _nose_profile(x):
    """Section of the nose for inside tests (same point count as a loft profile)."""
    x = min(x, X_FRONT - 1e-4)
    keys = _nose_keys(x)
    n_tot = 1 + sum(NSEG.values())
    P = _resample(np.array([(0.0, y, z) for (y, z) in keys]), n_tot)
    pts = [np.array([p[1], p[2]]) for p in P]
    tags = ['A'] * (n_tot // 2) + ['G'] * (n_tot - n_tot // 2)
    return pts, tags


KX = [-2.22, -2.10, -1.95, -1.70, -1.40, -1.10, -0.70, -0.30, 0.10, 0.50, 0.85, 1.05, 1.19, 1.40, 1.60, 1.75,
      1.84, 1.95, 2.08, 2.20]


def _ktables():
    fl, si, lc, sc, inn, rs, top = [], [], [], [], [], [], []
    for x in KX:
        if x <= X_LE:
            xx = max(x, X_TT)
            fl.append((ln('fly', xx), ln('flz', xx)))
            si.append((ln('sby', xx), ln('sbz', xx)))
            lc.append((ln('lcy', xx), ln('lcz', xx)))
            sc.append((ln('scy', xx), ln('scz', xx)))
            w = _wl_at(xx)
            r = _rail_at(xx)
            inn.append((float(w[0]), float(w[1])))
            rs.append((float(r[0]), float(r[1])))
            top.append(_top_at(xx))
        else:
            k = _nose_keys(min(x, X_FRONT - 1e-4))
            if x <= K_CORNER[0]:
                fl.append(k[1]); si.append(k[2]); lc.append(k[3]); sc.append(k[4]); inn.append(k[5])
                rs.append(k[5]); top.append(k[6][1])
            else:
                fl.append(k[1]); si.append(k[1]); lc.append(k[2]); sc.append(k[3]); inn.append(k[4])
                rs.append(k[4]); top.append(k[5][1])
    return fl, si, lc, sc, inn, rs, top


K_FLOOR, K_SILL, K_LC, K_SC, K_IN, K_RS, K_TOP = _ktables()


# ------------------------------------------------------------------ booleans, thickness
def _arch_cutter(col):
    bm = bmesh.new()
    for ax in (AX_F, AX_R):
        for side in (1, -1):
            prof = [(R_ARCH, 0.50 * side), (R_ARCH, 1.30 * side)]
            L.bm_lathe(bm, prof if side > 0 else prof[::-1], (ax, 0, R_WHEEL + ARCH_DZ), (0, 1, 0), seg=96,
                       close_start=True, close_end=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return L.bm_obj('RS2_archcut', bm, col)


def _hole_cutter(col):
    """Cylinders where nozzle parts pass through the skin: each lift nozzle's feed pipe up through the floor, each
    nose port through the pod's side (applied to the floor and the nose only)."""
    bm = bmesh.new()
    for nm, (p, d) in NOZZLES.items():
        p, d = Vector(p), Vector(d).normalized()
        if nm.startswith('lift'):
            L.bm_lathe(bm, [(0.0195, -0.03), (0.0195, -0.26)], p, d, seg=24, close_start=True, close_end=True)
        elif nm.startswith('nose'):
            L.bm_lathe(bm, [(0.0240, 0.02), (0.0240, -0.07)], p, d, seg=32, close_start=True, close_end=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return L.bm_obj('RS2_holecut', bm, col)


def _drop_port_walls(ob):
    """The exact boolean keeps the port cutters' walls and inner caps inside the nose fascia (it reads the fascia as
    enclosing a volume); remove them so the ports are clean holes."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    kill = []
    for nm, (p, d) in NOZZLES.items():
        if not nm.startswith('nose'):
            continue
        p, d = Vector(p), Vector(d).normalized()
        for f in bm.faces:
            c = f.calc_center_median()
            v = c - p
            dep = -v.dot(d)
            rr = (v + d * dep).length
            if rr < 0.0247 and (abs(f.normal.dot(d)) < 0.5 or dep > 0.02 or dep < -0.012):
                kill.append(f)
    if kill:
        bmesh.ops.delete(bm, geom=list(set(kill)), context='FACES')
    bm.to_mesh(ob.data)
    bm.free()


def apply_boolean(ob, cutter, op='DIFFERENCE'):
    mod = ob.modifiers.new('cut', 'BOOLEAN')
    mod.operation = op
    mod.solver = 'EXACT'
    mod.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    ob.modifiers.clear()
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)


FRIT_W = 0.040        # black ceramic frit band round each glass pane (m)
FRIT_SOFT = 0.006


def _add_frit(ob, width=FRIT_W, soft=FRIT_SOFT):
    """Point attribute 'frit' (1 within `width` of the pane's edge, fading over `soft`): the glass material draws the
    black frit band from it, so every pane has a crisp dark border against the white body."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    segs = np.array([[e.verts[0].co[:], e.verts[1].co[:]] for e in bm.edges if e.is_boundary], float)
    bm.free()
    P = np.array([v.co[:] for v in me.vertices], float)
    if not len(segs) or not len(P):
        return
    A, AB = segs[:, 0], segs[:, 1] - segs[:, 0]
    L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    d = np.empty(len(P))
    for i0 in range(0, len(P), 256):
        p = P[i0:i0 + 256, None, :]
        t = np.clip(((p - A[None]) * AB[None]).sum(2) / L2[None], 0.0, 1.0)
        q = A[None] + t[..., None] * AB[None]
        d[i0:i0 + 256] = np.sqrt(((p - q) ** 2).sum(2)).min(1)
    f = np.clip((width + soft - d) / soft, 0.0, 1.0)
    at = me.attributes.get('frit') or me.attributes.new('frit', 'FLOAT', 'POINT')
    at.data.foreach_set('value', f.astype(np.float32))


def finish_panel(ob, thick=0.007, bevel=0.0018, mat=None, even=True):
    if mat is not None:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    sol = ob.modifiers.new('shell', 'SOLIDIFY')
    sol.thickness = thick
    sol.offset = -1.0
    sol.use_even_offset = even          # off for the glass: its tapering tips would spike
    sol.use_quality_normals = True
    if bevel > 0:
        bv = ob.modifiers.new('edge', 'BEVEL')
        bv.width = bevel
        bv.segments = 2
        bv.limit_method = 'ANGLE'
        bv.angle_limit = math.radians(50)
        bv.harden_normals = False
        bv.miter_outer = 'MITER_ARC'
    return ob


# ------------------------------------------------------------------ wheels
def build_wheel(col, mats, name, ax, side):
    """Low-profile tyre (rounded shoulders, bulged sidewall with a rim protector, four tread grooves) and the stunt
    cars' plain wheel face (fact S10): polished rim lip, shallow satin dish, centre cap."""
    s = side
    hw = W_TIRE / 2
    R = R_WHEEL
    bm = bmesh.new()
    h = R - 0.262                                   # sidewall height above the rim seat
    prof = [(0.262, -hw + 0.016), (0.270, -hw + 0.004), (0.262 + 0.20 * h, -hw - 0.003),
            (0.262 + 0.37 * h, -hw - 0.006), (0.262 + 0.57 * h, -hw - 0.006), (0.262 + 0.73 * h, -hw - 0.002),
            (0.262 + 0.85 * h, -hw + 0.008), (0.262 + 0.93 * h, -hw + 0.020), (R - 0.002, -hw + 0.036),
            (R, -hw + 0.055)]
    tread = [(R, -hw + 0.055)]
    prof_full = prof + [(R, y) for y in np.linspace(-hw + 0.065, hw - 0.065, 9)] + \
        [(r, -y) for (r, y) in prof[::-1]]
    L.bm_lathe(bm, prof_full, (0, 0, 0), (0, 1, 0), seg=128)
    tyre = L.bm_obj(name + '_tyre', bm, col, smooth=True, mat=mats['tyre'])
    # tread grooves: dark rings sunk into the crown
    bm = bmesh.new()
    for off in (-0.082, -0.028, 0.028, 0.082):
        L.bm_lathe(bm, [(R - 0.006, off - 0.005), (R + 0.0006, off - 0.005), (R + 0.0006, off + 0.005),
                        (R - 0.006, off + 0.005)], (0, 0, 0), (0, 1, 0), seg=128)
    grooves = L.bm_obj(name + '_grooves', bm, col, smooth=True, mat=mats['groove'] if 'groove' in mats else mats['trim'])
    L.parent_keep_local(grooves, tyre)
    # polished rim lip on the outer face, inner barrel on the inner face
    bm = bmesh.new()
    lip = [(0.250, s * (hw - 0.012)), (0.262, s * (hw - 0.004)), (0.266, s * (hw + 0.004)), (0.262, s * (hw + 0.010)),
           (0.252, s * (hw + 0.011)), (0.244, s * (hw + 0.006))]
    L.bm_lathe(bm, lip, (0, 0, 0), (0, 1, 0), seg=128)
    rim = L.bm_obj(name + '_rim', bm, col, smooth=True, mat=mats.get('rim', mats['steel']))
    L.parent_keep_local(rim, tyre)
    # plain dished cover: flat outer ring, shallow dish, raised hub boss
    bm = bmesh.new()
    cov = [(0.244, s * (hw + 0.006)), (0.236, s * (hw + 0.004)), (0.215, s * (hw - 0.002)),
           (0.170, s * (hw - 0.012)), (0.110, s * (hw - 0.020)), (0.070, s * (hw - 0.018)),
           (0.058, s * (hw - 0.012)), (0.050, s * (hw - 0.006)), (0.0, s * (hw - 0.005))]
    L.bm_lathe(bm, cov, (0, 0, 0), (0, 1, 0), seg=128)
    L.bm_lathe(bm, [(0.0, -s * (hw - 0.012)), (0.262, -s * (hw - 0.014))], (0, 0, 0), (0, 1, 0), seg=64)
    cover = L.bm_obj(name + '_cover', bm, col, smooth=True, mat=mats['cover'])
    L.parent_keep_local(cover, tyre)
    # centre cap and a fine machined groove ring
    bm = bmesh.new()
    L.bm_lathe(bm, [(0.0, s * (hw - 0.001)), (0.030, s * (hw - 0.002)), (0.043, s * (hw - 0.006)),
                    (0.047, s * (hw - 0.010))], (0, 0, 0), (0, 1, 0), seg=64)
    L.bm_lathe(bm, [(0.198, s * (hw - 0.0062)), (0.201, s * (hw - 0.0035)), (0.204, s * (hw - 0.0062))],
               (0, 0, 0), (0, 1, 0), seg=128)
    cap = L.bm_obj(name + '_cap', bm, col, smooth=True, mat=mats['dark_metal'])
    L.parent_keep_local(cap, tyre)
    tyre.location = (ax, side * TRACK_Y, R_WHEEL)
    tyre.rotation_mode = 'XYZ'
    return tyre


def build_wheels(col, mats):
    out = []
    for ax in (AX_F, AX_R):
        for side in (1, -1):
            out.append(build_wheel(col, mats, f'RS2_wheel_{"F" if ax > 0 else "R"}{"L" if side > 0 else "R"}', ax, side))
    # wheel wells: liner arch (above the floor) plus an inner wall so the body does not read hollow through the arch
    bm = bmesh.new()
    cz = R_WHEEL + ARCH_DZ
    for ax in (AX_F, AX_R):
        for side in (1, -1):
            n = 56
            a0, a1 = math.radians(-8), math.radians(188)
            outer, inner = [], []
            for k in range(n + 1):
                a = a0 + (a1 - a0) * k / n
                xx, zz = ax + (R_ARCH - 0.002) * math.cos(a), cz + (R_ARCH - 0.002) * math.sin(a)
                outer.append(bm.verts.new((xx, side * 0.975, zz)))
                inner.append(bm.verts.new((xx, side * 0.640, zz)))
            for k in range(n):
                q = (outer[k], outer[k + 1], inner[k + 1], inner[k])
                bm.faces.new(q if side > 0 else q[::-1])
            # inner wall (disc segment at |y| = 0.64) down to the floor
            ctr = bm.verts.new((ax, side * 0.640, max(cz - 0.12, 0.25)))
            for k in range(n):
                q = (inner[k], inner[k + 1], ctr)
                bm.faces.new(q if side > 0 else q[::-1])
    liner = L.bm_obj('RS2_liners', bm, col, smooth=False, mat=mats['under'])
    me = liner.data
    bm = bmesh.new()
    bm.from_mesh(me)
    kill = [f for f in bm.faces if f.calc_center_median().z < 0.215]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(me)
    bm.free()
    return out, liner


# ------------------------------------------------------------------ tail
def _ring_outline(x_stat):
    """Deformed last loft ring (closed loop, car-local)."""
    half, _ = profile_at(x_stat)
    ring = [(x_stat, p[0], p[1]) for p in half] + [(x_stat, -p[0], p[1]) for p in half[-2:0:-1]]
    return [(x + _tail_shift(x, z), y, z) for (x, y, z) in ring]


def _clip_band(poly, za, zb):
    """Sutherland-Hodgman clip of a closed 2D polygon [(y, z)] to the band za <= z <= zb."""
    def clip(pts, keep, zc):
        out = []
        n = len(pts)
        for i in range(n):
            P, Q = pts[i], pts[(i + 1) % n]
            kp, kq = keep(P), keep(Q)
            if kp:
                out.append(P)
            if kp != kq:
                t = (zc - P[1]) / (Q[1] - P[1])
                out.append((P[0] + t * (Q[0] - P[0]), zc))
        return out
    pts = clip(poly, lambda p: p[1] >= za, za)
    return clip(pts, lambda p: p[1] <= zb, zb) if pts else pts


def _circle(cy, cz, r, n=40):
    return [(cy + r * math.cos(2 * math.pi * k / n), cz + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _cap_region(ring, zlo, zhi, name, col, mat, dx=0.0, holes=(), yscale=1.0):
    """Cap of the deformed tail ring between two heights: one flat piece per undercut band (vertical above the fold,
    tilted to the split, vertical below), each clipped from the ring outline and filled; `holes` are closed (y, z)
    loops cut out of the piece that contains them."""
    from mathutils.geometry import tessellate_polygon
    poly = [(p[1] * yscale, p[2]) for p in ring]
    cuts = sorted(set([zlo, zhi] + [z for z in (Z_FOLD, Z_SPLIT) if zlo < z < zhi]))
    bm = bmesh.new()
    for za, zb in zip(cuts[:-1], cuts[1:]):
        clean = []
        for p in _clip_band(poly, za, zb):
            if not clean or abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1]) > 1e-6:
                clean.append(p)
        while len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) + abs(clean[0][1] - clean[-1][1]) < 1e-6:
            clean.pop()
        if len(clean) < 3:
            continue
        loops = [clean] + [h for h in holes if all(za + 0.004 < q[1] < zb - 0.004 for q in h)]
        flat = [q for lp in loops for q in lp]
        vs = [bm.verts.new((X_TT + dx + _tail_u(z), y, z)) for (y, z) in flat]
        for t in tessellate_polygon([[Vector((y, z, 0.0)) for (y, z) in lp] for lp in loops]):
            try:
                bm.faces.new([vs[i] for i in t])
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.x > 0:
            f.normal_flip()
    return L.bm_obj(name, bm, col, smooth=False, mat=mat)


def build_tail(col, mats):
    """Tail: white panel with the full-width light band and the plate on its undercut; below it the diffuser with
    the nozzle bar, four round fan openings and fins."""
    objs = {}
    ring = _ring_outline(X_TT)
    objs['fascia'] = _cap_region(ring, Z_SPLIT, 2.0, 'RS2_tail_panel', col, mats['paint'])
    # light band: black glass over the top of the tail (a trapezoid following the tail outline, a white lip left
    # round it), the red LED line across its middle
    zb0, zb1 = Z_FOLD + 0.008, Z_FOLD + 0.112
    band = _cap_region(ring, zb0, zb1, 'RS2_tail_band', col, mats['gloss_black'], dx=-0.004, yscale=0.985)
    sol = band.modifiers.new('t', 'SOLIDIFY')
    sol.thickness = 0.008
    sol.offset = 1.0
    objs['band'] = band
    zl = 0.5 * (zb0 + zb1) - 0.004
    ys = [abs(p[1]) * 0.985 for p in ring if abs(p[2] - zl) < 0.03]
    hw = (max(ys) if ys else 0.84) - 0.025
    bt = bmesh.new()
    pts = [(X_TT - 0.0135, y, zl) for y in np.linspace(-hw, hw, 60)]
    L.bm_tube_along(bt, pts, 0.0048, seg=8)
    objs['light'] = L.bm_obj('RS2_tail_light', bt, col, smooth=True, mat=mats['taillight'])
    # plate on the undercut panel (build_plate: surround, lit plate, characters, border, lamp)
    objs.update(build_plate(col, mats, objs['fascia']))
    # diffuser: black lower cap of the ring with four round fan openings
    holes = [_circle(fy, fz, FAN_R + 0.010, 48)[::-1] for (fx, fy, fz) in FANS]
    holes += [_circle(p[1], p[2], 0.0400, 32)[::-1] for nm, (p, d) in NOZZLES.items() if nm.startswith('rear')]
    lower = _cap_region(ring, -1.0, Z_SPLIT, 'RS2_tail_diffuser', col, mats.get('diffuser', mats['trim']), holes=holes)
    sol = lower.modifiers.new('t', 'SOLIDIFY')
    sol.thickness = 0.012
    sol.offset = 1.0
    objs['diffuser'] = lower
    # nozzle bar across the top of the diffuser, just behind the plate, with a hole for each rear nozzle (they bolt
    # to its rear face); its ends sit in the side plates of the fan module
    bm = bmesh.new()
    xb = X_TT + 0.075
    _plate_with_holes(bm, X_NBAR1, X_NBAR0, -0.618, 0.618, Z_NBAR[0], Z_NBAR[1],
                      [(p[1], p[2], 0.0395) for nm, (p, d) in NOZZLES.items() if nm.startswith('rear')])
    objs['nozbar'] = L.bm_obj('RS2_tail_nozbar', bm, col, mat=mats.get('diffuser', mats['frame_dark']))
    # fan module frame (FAN_FRAME): polished side plates and a bottom bar framing four bays, three dark dividers;
    # their front edges sit 1 mm into the diffuser plate's rear face
    bm = bmesh.new()
    ff = FAN_FRAME
    xf = xb - 0.0110
    for y in (0.0, 0.31, -0.31):
        prof = [(xf, Z_NBAR[0] - 0.002), (xb - 0.060, Z_NBAR[0] - 0.010), (xb - 0.085, 0.20),
                (xb - 0.088, ff['zb'] + 0.012), (xf, ff['zb'] + 0.012)]
        _fin(bm, prof, y, 0.008, mi=1)
    for s in (1, -1):
        prof = [(xf, ff['zt'] - 0.007), (xb - 0.050, ff['zt'] - 0.015), (xb - 0.095, 0.30),
                (xb - 0.102, ff['zb']), (xf, ff['zb'])]
        _fin(bm, prof, s * ff['top'], 0.012, mi=0)
    L.bm_box(bm, ((xf + xb - 0.102) / 2, 0.0, ff['zb'] + 0.006), (xf - (xb - 0.102), 2 * ff['bot'], 0.012))
    # dark plates (m064 / m057: the lower tail is black, so the gold nozzle rings and the lit plate stand out)
    objs['fins'] = L.bm_obj('RS2_tail_fins', bm, col, mat=[mats.get('frame_dark', mats['frame']), mats['trim']])
    return objs


# ------------------------------------------------------------------ plate
PLATE_TEXT = 'RS 02'           # generic characters, not a real registration
PLATE_W, PLATE_H = 0.305, 0.152
PLATE_LAMP_W = 2.5             # plate lamp power (W): the plate reads lit at night, a soft pool on the panel round it


def _plate_frame():
    """(origin on the undercut panel at the plate centre, ex = the viewer's right seen from behind (car -y), ey = up
    along the panel, ez = out of the panel (back and down))."""
    zc = 0.5 * (Z_FOLD + Z_SPLIT) - 0.01
    tilt = math.atan2(U_TAIL, Z_FOLD - Z_SPLIT)
    o = Vector((X_TT + _tail_shift(X_TT, zc), 0.0, zc))
    ey = Vector((-math.sin(tilt), 0.0, math.cos(tilt)))
    ez = Vector((-math.cos(tilt), 0.0, -math.sin(tilt)))
    ex = Vector((0.0, -1.0, 0.0))
    return o, ex, ey, ez


def _plate_box(bm, o, ex, ey, ez, w, h, z0, z1):
    """Box on the panel frame: w x h in the panel plane, from z0 to z1 out of it."""
    c = o + ez * (0.5 * (z0 + z1))
    R = Matrix((ex, ey, ez)).transposed().to_4x4()
    L.bm_box(bm, c, (w, h, z1 - z0), rot=R)


def _text_mesh(col, text, height, max_w):
    """Mesh of `text` in Blender's built-in font, centred on the origin in its xy plane (+z out), scaled so its
    characters are `height` tall (and no wider than max_w), 0.6 mm thick."""
    cu = bpy.data.curves.new('RS2_tmp_text', 'FONT')
    cu.body = text
    cu.size = 1.0
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.extrude = 0.5
    ob = bpy.data.objects.new('RS2_tmp_text', cu)
    col.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    if not len(me.vertices):
        return me
    co = np.array([v.co[:] for v in me.vertices])
    lo, hi = co.min(0), co.max(0)
    s = min(height / max(hi[1] - lo[1], 1e-6), max_w / max(hi[0] - lo[0], 1e-6))
    ctr = 0.5 * (lo + hi)
    me.transform(Matrix.Diagonal((s, s, 0.0006 / max(hi[2] - lo[2], 1e-6), 1.0)) @ Matrix.Translation(-Vector(ctr)))
    return me


def build_plate(col, mats, panel):
    """Rear plate as a real part (m057 / m064 / m071: a plain white plate under the light band): a gloss-black
    surround on the undercut panel, the white plate lit by its lamp (glowing face plus a real lamp light in the
    surround's top edge that also throws a soft pool on the panel), generic dark characters and a printed border.
    Everything is parented to the plate (RS2_tail_plate), which the bullet-time peel moves with the tail cap."""
    o, ex, ey, ez = _plate_frame()
    out = {}
    bm = bmesh.new()
    _plate_box(bm, o, ex, ey, ez, PLATE_W, PLATE_H, 0.004, 0.0075)
    plate = L.bm_obj('RS2_tail_plate', bm, col, mat=mats['plate'])
    out['plate'] = plate
    bm = bmesh.new()
    _plate_box(bm, o, ex, ey, ez, PLATE_W + 0.060, PLATE_H + 0.040, -0.002, 0.004)
    # lamp hood along the surround's top edge, over the plate
    _plate_box(bm, o + ey * (PLATE_H / 2 + 0.012), ex, ey, ez, 0.150, 0.012, 0.004, 0.016)
    surround = L.bm_obj('RS2_plate_surround', bm, col, mat=mats['gloss_black'])
    L.parent_keep_local(surround, plate)
    # characters and a printed border, 0.2 mm proud of the face
    face = o + ez * 0.0075
    R = Matrix((ex, ey, ez)).transposed().to_4x4()
    me = _text_mesh(col, PLATE_TEXT, 0.074, PLATE_W - 0.05)
    me.transform(Matrix.Translation(face + ez * 0.0005 - ey * 0.004) @ R)
    ink = bpy.data.objects.new('RS2_plate_text', me)
    col.objects.link(ink)
    me.materials.append(mats.get('plate_ink', mats['gloss_black']))
    bm = bmesh.new()
    bw, bh, t = PLATE_W - 0.014, PLATE_H - 0.014, 0.0035
    for (cx, cy, w, h) in ((0.0, bh / 2, bw, t), (0.0, -bh / 2, bw, t), (bw / 2, 0.0, t, bh), (-bw / 2, 0.0, t, bh)):
        _plate_box(bm, face + ex * cx + ey * cy, ex, ey, ez, w, h, 0.0, 0.0004)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    border = L.bm_obj('RS2_plate_border', bm, col, mat=mats.get('plate_ink', mats['gloss_black']))
    for ob in (ink, border):
        L.parent_keep_local(ob, plate)
    # lamp: a lens strip under the hood, and the light itself (only the tail panel and the plate parts receive it)
    bm = bmesh.new()
    _plate_box(bm, o + ey * (PLATE_H / 2 + 0.0075), ex, ey, ez, 0.130, 0.002, 0.008, 0.015)
    lens = L.bm_obj('RS2_plate_lamp', bm, col, mat=mats.get('plate_lamp', mats['headlamp']))
    L.parent_keep_local(lens, plate)
    ld = bpy.data.lights.new('RS2_plate_lamp', 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y = 0.13, 0.008
    ld.energy = PLATE_LAMP_W
    ld.color = (1.0, 0.97, 0.92)
    lamp = bpy.data.objects.new('RS2_plate_lamp_light', ld)
    col.objects.link(lamp)
    # at the lens, aimed down the plate and a little out of it
    pos = o + ey * (PLATE_H / 2 + 0.010) + ez * 0.020
    aim = o - ey * 0.04 + ez * 0.004
    lamp.location = pos
    lamp.rotation_mode = 'QUATERNION'
    lamp.rotation_quaternion = L.look_quat(pos, aim, tuple(ez))
    for attr in ('visible_camera', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter'):
        if hasattr(lamp, attr):
            setattr(lamp, attr, False)
    llp = bpy.data.collections.new('LL_plate_lamp')
    for ob in (plate, surround, ink, border, panel):
        llp.objects.link(ob)
    lamp.light_linking.receiver_collection = llp
    L.parent_keep_local(lamp, plate)
    out.update(surround=surround, plate_text=ink, plate_border=border, plate_lens=lens, plate_lamp=lamp)
    return out


def _fin(bm, prof, y, th, mi=0):
    """Thin plate in the xz-plane at lateral position y from a closed (x, z) outline."""
    v0 = [bm.verts.new((x, y - th / 2, z)) for (x, z) in prof]
    v1 = [bm.verts.new((x, y + th / 2, z)) for (x, z) in prof]
    fs = [bm.faces.new(v0[::-1]), bm.faces.new(v1)]
    n = len(prof)
    for k in range(n):
        j = (k + 1) % n
        fs.append(bm.faces.new((v0[k], v0[j], v1[j], v1[k])))
    for f in fs:
        f.material_index = mi


# ------------------------------------------------------------------ assembly
PAINT_PANELS = ('fender_L', 'fender_R', 'door_L', 'door_R', 'quarter_L', 'quarter_R', 'hood', 'deck')


def build_hood(col, mats):
    S = hood_grid()
    S = shrink_grid(S)
    bm = bmesh.new()
    grid_bm(bm, S)
    ob = L.bm_obj('RS2_hood', bm, col, smooth=True, mat=mats['paint'])
    return ob


def build_car(col, mats):
    panels, grid = build_panels(col, mats)
    panels['hood'] = build_hood(col, mats)
    front = build_front(col, mats)
    panels['nose'] = front['face']
    cutter = _arch_cutter(col)
    for nm in ('fender_L', 'fender_R', 'quarter_L', 'quarter_R', 'sill_L', 'sill_R', 'floor', 'nose'):
        if nm in panels:
            apply_boolean(panels[nm], cutter)
    for nm in ('airdam', 'frontcap'):
        apply_boolean(front[nm], cutter)
    bpy.data.objects.remove(cutter)
    holes = _hole_cutter(col)
    for nm in ('floor', 'nose'):
        apply_boolean(panels[nm], holes)
    _drop_port_walls(panels['nose'])
    bpy.data.objects.remove(holes)
    for nm, ob in panels.items():
        if nm not in ('hood', 'nose', 'floor'):
            # the loft's faces come out facing into the car; face them out so the shell (offset -1) grows inward and
            # the painted / glazed surface stays on the design surface, flush with the hood and the nose patches
            # (the floor keeps its upward faces: its shell hangs below the cabin floor)
            ob.data.flip_normals()
    for nm, ob in panels.items():
        if nm in PAINT_PANELS:
            finish_panel(ob, mat=mats['paint'])
        elif nm == 'nose':
            finish_panel(ob)
        elif nm in ('canopy', 'rearglass'):
            _add_frit(ob)
            finish_panel(ob, thick=0.006, bevel=0.0, mat=mats['glass'], even=False)
        elif nm.startswith('sill'):
            finish_panel(ob, thick=0.004, mat=mats['trim'])
        elif nm == 'floor':
            finish_panel(ob, thick=0.004, bevel=0.0, mat=mats['under'])
    wheels, liner = build_wheels(col, mats)
    tail = build_tail(col, mats)
    split = build_splitter(col, mats)
    noz = build_nozzles(col, mats)
    fans, duct = build_fans(col, mats)
    grid_, fpanels, skirt = build_underbody(col, mats)
    details = build_details(col, mats, panels)
    import car_interior as CI
    inner = CI.build_all(col, mats)
    return dict(panels=panels, wheels=wheels, liner=liner, tail=tail, front=front, splitter=split, nozzles=noz,
                fans=fans, duct=duct, gridframe=grid_, floorpanels=fpanels, skirt=skirt, details=details,
                inner=inner)


# ------------------------------------------------------------------ hardware shared with the effects
# Ten nozzles (fact table S65): four rear (push), one behind each wheel pointing down, two at the nose pointing
# sideways. Each position is the nozzle's exit centre, each direction its exit axis.
def _nose_port():
    """Point on the pod's side just ahead of the front arch where the nose nozzle exits (left)."""
    S = pod_grid().reshape(-1, 3)
    k = int(np.argmin((S[:, 0] - 1.850) ** 2 + (S[:, 2] - 0.400) ** 2))
    return round(float(S[k, 1]) + 0.002, 4)


_YN = _nose_port()
NOZZLES = {
    'rear_1': ((-2.180, 0.353, 0.480), (-1, 0, 0)),
    'rear_2': ((-2.180, 0.118, 0.480), (-1, 0, 0)),
    'rear_3': ((-2.180, -0.118, 0.480), (-1, 0, 0)),
    'rear_4': ((-2.180, -0.353, 0.480), (-1, 0, 0)),
    'lift_FL': ((0.800, 0.902, 0.105), (0, 0, -1)),
    'lift_FR': ((0.800, -0.902, 0.105), (0, 0, -1)),
    'lift_RL': ((-1.990, 0.800, 0.100), (0, 0, -1)),
    'lift_RR': ((-1.990, -0.800, 0.100), (0, 0, -1)),
    'nose_L': ((1.850, _YN, 0.400), (0, 1, 0)),
    'nose_R': ((1.850, -_YN, 0.400), (0, -1, 0)),
}
FAN_FRAME = dict(top=0.62, bot=0.62, zt=0.555, zb=0.14)     # diffuser module (fan bays), half-widths and heights
FAN_R = 0.115
FANS = [(-2.050, y, 0.305) for y in (0.465, 0.155, -0.155, -0.465)]
SKIRT = dict(x0=-1.02, x1=1.02, hy=0.87, z_top=0.165, z_bot=0.006, corner=0.14)
# tanks, valves, manifold and pipes: car_interior.py


def _underside_z(x, y):
    """Height of the body's underside (floor, its edge and the sill bottom) at plan position (x, |y|)."""
    half, tags = profile_at(x)
    pts = [p for p, t in zip(half, tags) if t in ('A', 'B')]
    ys = np.array([float(p[0]) for p in pts])
    zs = np.array([float(p[1]) for p in pts])
    o = np.argsort(ys)
    return float(np.interp(min(y, ys.max()), ys[o], zs[o]))


def _lathe_obj(bm, prof, p, d, seg=40):
    L.bm_lathe(bm, prof, p, d, seg=seg)


def _pod_bvh(side):
    """BVH of the pod's front face (design surface, side +1 left / -1 right)."""
    from mathutils.bvhtree import BVHTree
    S = pod_grid()
    if side < 0:
        S = mirror_grid(S)
    nu, nv = S.shape[0], S.shape[1]
    verts = [tuple(S[i, j]) for i in range(nu) for j in range(nv)]
    faces = [(i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1)
             for i in range(nu - 1) for j in range(nv - 1)]
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def _nose_port_part(bm, bk, p, d, tree):
    """Flush side port: a polished bezel ring following the pod's skin round the hole (cut by _hole_cutter), the
    tube going in along the jet axis, a dark plug 3 cm deep, a flange inside the skin and the feed stub."""
    e1 = Vector((1.0, 0.0, 0.0))
    e2 = d.cross(e1).normalized()
    n = 40

    def skin(r, a):
        o = (e1 * math.cos(a) + e2 * math.sin(a)) * r
        hit = tree.ray_cast(p + o + d * 0.05, -d, 0.2)[0]
        return hit if hit is not None else p + o - d * 0.002
    rings = []
    for (r, h) in ((0.0200, 0.0012), (0.0275, 0.0012), (0.0310, -0.0008)):
        rings.append([bm.verts.new(skin(r, 2 * math.pi * k / n) + d * h) for k in range(n)])
    deep = [bm.verts.new(p + (e1 * math.cos(2 * math.pi * k / n) + e2 * math.sin(2 * math.pi * k / n)) * 0.0200
                         - d * 0.050) for k in range(n)]
    for ra, rb in ((deep, rings[0]), (rings[0], rings[1]), (rings[1], rings[2])):
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((ra[k], ra[j], rb[j], rb[k]))
    L.bm_lathe(bk, [(0.0199, -0.030), (0.0, -0.030)], p, d, seg=32)                       # dark plug
    L.bm_lathe(bk, [(0.0205, -0.034), (0.045, -0.034), (0.045, -0.040), (0.0205, -0.040)], p, d, seg=32)
    L.bm_tube_along(bk, [p - d * 0.040, p - d * 0.075], 0.016, seg=16)


def _plate_with_holes(bm, x0, x1, y0, y1, z0, z1, holes, seg=32):
    """Closed box x0..x1 (x0 < x1) by y0..y1 by z0..z1 with round holes along x: holes = [(y, z, r)]."""
    from mathutils.geometry import tessellate_polygon
    outline = [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]
    loops = [outline] + [[(hy + r * math.cos(2 * math.pi * k / seg), hz - r * math.sin(2 * math.pi * k / seg))
                          for k in range(seg)] for (hy, hz, r) in holes]
    flat = [q for lp in loops for q in lp]
    tris = tessellate_polygon([[Vector((y, z, 0.0)) for (y, z) in lp] for lp in loops])
    for x, flip in ((x0, False), (x1, True)):
        vs = [bm.verts.new((x, y, z)) for (y, z) in flat]
        for t in tris:
            f = [vs[i] for i in t]
            bm.faces.new(f[::-1] if flip else f)
    for lp in loops:
        a = [bm.verts.new((x0, y, z)) for (y, z) in lp]
        b = [bm.verts.new((x1, y, z)) for (y, z) in lp]
        for k in range(len(lp)):
            j = (k + 1) % len(lp)
            bm.faces.new((a[k], a[j], b[j], b[k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


# rear nozzle bar: just behind the diffuser plate (its rear face is at X_TT + U_TAIL - 0.012)
X_NBAR0 = X_TT + U_TAIL - 0.0135
X_NBAR1 = X_TT + U_TAIL - 0.045
Z_NBAR = (0.437, 0.523)


def build_nozzles(col, mats):
    """Every nozzle is a part: exit bell, throat, body, mounting flange with bolts, bracket to the structure and a
    feed pipe running into the car (the interior's pipes end at the inlet, p - d * 0.175 / 0.11 / 0.075). Where a
    part passes through a panel the panel has a hole (_hole_cutter; the tail's diffuser and nozzle bar)."""
    objs = {}
    trees = {}
    for nm, (p, d) in NOZZLES.items():
        p, d = Vector(p), Vector(d).normalized()
        bm = bmesh.new()      # bright metal (bell, lip)
        bk = bmesh.new()      # dark parts (flange, bracket, bolts, pipe)
        if nm.startswith('lift'):
            # exit bell, throat and body up to a flange plate hung just under the floor (axial coordinate against d:
            # negative = up into the car); the floor's shell is 4 mm thick, the flange stops 0.5 mm below it
            zt = min(_underside_z(p.x, abs(p.y) + dy) for dy in np.linspace(-0.034, 0.034, 9)) - 0.0050
            lb = max(0.050, zt - 0.008 - p.z)
            bell = [(0.036, 0.0), (0.041, 0.0), (0.040, -0.008), (0.032, -0.028), (0.024, -0.042), (0.021, -0.047),
                    (0.024, -0.052), (0.028, -0.056), (0.028, -(lb - 0.004)), (0.024, -lb), (0.016, -lb)]
            L.bm_lathe(bm, bell, p, d, seg=40)
            L.bm_lathe(bk, [(0.034, -0.004), (0.034, -0.002), (0.0, -0.002)], p, d, seg=24)   # dark throat plug
            top = p - d * lb                                      # bottom face of the flange
            L.bm_box(bk, top - d * 0.004, (0.096, 0.064, 0.008))
            for (bx, by) in ((0.036, 0.022), (-0.036, 0.022), (0.036, -0.022), (-0.036, -0.022)):
                L.bm_lathe(bk, [(0.0065, 0.0), (0.0065, 0.004), (0.0, 0.004)], top + Vector((bx, by, 0.0)), d, seg=6)
            # feed pipe: straight up through the floor (hole) to the inlet, then an elbow toward the car's centre
            inlet = p - d * 0.175
            L.bm_tube_along(bk, [top - d * 0.004, inlet], 0.017, seg=16)
            inward = Vector((0, -math.copysign(1, p.y), 0))
            L.bm_tube_along(bk, [inlet + d * 0.004, inlet - d * 0.03, inlet - d * 0.045 + inward * 0.02,
                                 inlet - d * 0.05 + inward * 0.07], 0.017, seg=16)
            # two gusset plates from the flange down the nozzle body (fore and aft)
            for sx in (1, -1):
                L.bm_box(bk, top + d * (0.375 * lb) + Vector((sx * 0.030, 0, 0)), (0.006, 0.030, lb * 0.75))
        elif nm.startswith('nose'):
            side = 1 if p.y > 0 else -1
            if side not in trees:
                trees[side] = _pod_bvh(side)
            _nose_port_part(bm, bk, p, d, trees[side])
        else:
            # rear: a big brushed-gold bezel round the same exit (m064's bright rings, m041's thick lips): rolled
            # inner lip, a face ring, a rounded outer edge and a short barrel back to the diffuser plate (its end
            # buried in the plate); the tube goes on through the diffuser and the nozzle bar (both have holes), a
            # flange bolted to the bar's rear face, feed pipe forward
            L.bm_lathe(bm, [(0.034, -0.120), (0.034, -0.008), (0.0352, -0.0028), (0.0378, -0.0002), (0.0420, 0.0009),
                            (0.0545, 0.0002), (0.0575, -0.0030), (0.0585, -0.0100), (0.0585, -0.0460),
                            (0.0385, -0.0460), (0.0385, -0.0950)], p, d, seg=64)
            L.bm_lathe(bk, [(0.0335, -0.012), (0.0335, -0.040), (0.0, -0.040)], p, d, seg=32)        # dark throat
            fl_c = Vector((X_NBAR1 - 0.0003, p.y, p.z))           # flange on the bar's rear face
            L.bm_lathe(bk, [(0.0386, 0.0035), (0.050, 0.0035), (0.050, 0.0), (0.0386, 0.0)], fl_c, d, seg=32)
            for k in range(4):
                a = math.pi / 4 + k * math.pi / 2
                off = Vector((0.0, math.cos(a) * 0.044, math.sin(a) * 0.044))
                L.bm_lathe(bk, [(0.004, 0.0035), (0.004, 0.0065), (0.0, 0.0065)], fl_c + off, d, seg=6)
            L.bm_tube_along(bk, [p - d * 0.10, p - d * 0.115], 0.017, seg=16)
        ob = L.bm_obj('RS2_noz_' + nm, bm, col, smooth=True,
                      mat=mats.get('nozzle', mats['steel']) if nm.startswith('rear') else mats['steel'])
        ob2 = L.bm_obj('RS2_nozmount_' + nm, bk, col, smooth=True, mat=mats['dark_metal'])
        L.parent_keep_local(ob2, ob)
        objs[nm] = ob
    return objs


def build_fans(col, mats):
    """Four ducted fans behind the round openings: blades and spinner hub turn (object x axis); housings, bellmouth
    lips and stator struts stay (the 'duct' object)."""
    fans = []
    nb = 9
    for i, (fx, fy, fz) in enumerate(FANS):
        bm = bmesh.new()
        L.bm_lathe(bm, [(0.0, -0.045), (0.024, -0.042), (0.036, -0.020), (0.038, 0.0), (0.036, 0.030),
                        (0.020, 0.045), (0.0, 0.048)], (0, 0, 0), (-1, 0, 0), seg=32)
        for k in range(nb):
            a0 = 2 * math.pi * k / nb
            rows = []
            for r in np.linspace(0.036, FAN_R - 0.004, 7):
                t = (r - 0.036) / (FAN_R - 0.040)
                sweep = 0.10 + 0.32 * t           # blades sweep back toward the tip
                chord = 0.42 - 0.12 * t           # radians of arc covered
                pitch = 0.016 * (1 - 0.6 * t)     # axial twist
                row = []
                for c in np.linspace(-0.5, 0.5, 5):
                    a = a0 + sweep + c * chord
                    ax_ = -c * pitch * 2
                    row.append(bm.verts.new((ax_, r * math.cos(a), r * math.sin(a))))
                rows.append(row)
            for ri in range(len(rows) - 1):
                for ci in range(4):
                    bm.faces.new((rows[ri][ci], rows[ri][ci + 1], rows[ri + 1][ci + 1], rows[ri + 1][ci]))
        ob = L.bm_obj(f'RS2_fan_{i}', bm, col, smooth=True, mat=mats.get('fan', mats['dark_metal']))
        sol = ob.modifiers.new('t', 'SOLIDIFY')
        sol.thickness = 0.0035
        ob.location = (fx, fy, fz)
        ob.rotation_mode = 'XYZ'
        fans.append(ob)
    bm = bmesh.new()
    xb = X_TT + 0.075
    for (fx, fy, fz) in FANS:
        c = Vector((fx, fy, fz))
        # housing from just inside the diffuser's opening forward to the back plate (axial coordinate along -x)
        a0 = fx - (xb + 0.001)
        L.bm_lathe(bm, [(FAN_R + 0.004, a0), (FAN_R + 0.008, a0 - 0.006), (FAN_R + 0.008, -0.16),
                        (FAN_R + 0.012, -0.17)], c, (-1, 0, 0), seg=64)
        # stator struts behind the blades (static) and a back plate
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            p0 = c + Vector((0.055, 0.03 * math.cos(a), 0.03 * math.sin(a)))
            p1 = c + Vector((0.055, (FAN_R + 0.008) * math.cos(a), (FAN_R + 0.008) * math.sin(a)))
            L.bm_strut(bm, p0, p1, 0.006, seg=6)
        L.bm_lathe(bm, [(0.0, -0.16), (FAN_R + 0.008, -0.16)], c, (-1, 0, 0), seg=48)
    duct = L.bm_obj('RS2_ducts', bm, col, smooth=True, mat=mats['dark_metal'])
    return fans, duct


def build_underbody(col, mats):
    """5 x 4 grid frame of light-grey box bars with dark panels in each bay (fact S17), inside a flexible ground seal
    (fact S18): a rigid dark rail under the floor, a rubber curtain and a brush strip on the road, set inboard of the
    sills so the white body overhangs it."""
    sk = SKIRT
    bm = bmesh.new()
    # bars kept clear of the seal's rail, which leans in under the floor (corners included)
    xs = np.linspace(sk['x0'] + 0.11, sk['x1'] - 0.11, 6)
    ys = np.linspace(-sk['hy'] + 0.11, sk['hy'] - 0.11, 5)
    zc = 0.150
    hb, wb = 0.036, 0.040
    for x in xs:
        L.bm_box(bm, (x, 0, zc), (wb, ys[-1] - ys[0] + wb, hb))
    for y in ys:
        L.bm_box(bm, ((xs[0] + xs[-1]) / 2, y, zc), (xs[-1] - xs[0] + wb, wb, hb))
    # gussets at the nodes
    for x in xs:
        for y in ys:
            L.bm_box(bm, (x, y, zc - hb / 2 - 0.002), (0.075, 0.075, 0.004))
    grid = L.bm_obj('RS2_gridframe', bm, col, mat=mats['frame'])
    bm = bmesh.new()
    for i in range(5):
        for j in range(4):
            cx = (xs[i] + xs[i + 1]) / 2
            cy = (ys[j] + ys[j + 1]) / 2
            L.bm_box(bm, (cx, cy, zc + 0.006), (xs[1] - xs[0] - wb - 0.008, ys[1] - ys[0] - wb - 0.008, 0.010))
    panels = L.bm_obj('RS2_floorpanels', bm, col, mat=mats['floorpanel'])
    # seal: rail (upper), curtain (middle, slightly flared), brush (bottom)
    loop = []
    r = sk['corner']
    cx0, cx1, hy = sk['x0'] + r, sk['x1'] - r, sk['hy'] - r
    for (cx, cy, a0) in ((cx1, hy, 0), (cx0, hy, 90), (cx0, -hy, 180), (cx1, -hy, 270)):
        for k in range(10):
            a = math.radians(a0 + 90 * k / 9)
            loop.append((cx + r * math.cos(a), cy + r * math.sin(a), math.cos(a), math.sin(a)))
    n = len(loop)
    # the curtain leans in under the floor at the top (the sills overhang it) and flares onto the road at the brush
    levels = [(sk['z_top'], -0.032, 0), (0.142, -0.028, 0), (0.136, -0.026, 1), (0.052, -0.004, 1), (0.042, 0.000, 2),
              (sk['z_bot'], 0.018, 2)]
    bm = bmesh.new()
    rings = []
    for (z, flare, mi) in levels:
        rings.append([bm.verts.new((x + nx * flare, y + ny * flare, z)) for (x, y, nx, ny) in loop])
    for li in range(len(levels) - 1):
        for k in range(n):
            j = (k + 1) % n
            f = bm.faces.new((rings[li][k], rings[li][j], rings[li + 1][j], rings[li + 1][k]))
            f.material_index = [0, 0, 1, 1, 2][li]
    skirt = L.bm_obj('RS2_skirt', bm, col, smooth=True,
                     mat=[mats['under'], mats['skirt'], mats.get('brush', mats['skirt'])])
    sol = skirt.modifiers.new('t', 'SOLIDIFY')
    sol.thickness = 0.012
    sol.offset = 0.0
    return grid, panels, skirt


def body_bvh(panels):
    """BVH of the closed outer body (all panels), car-local, from the unmodified panel meshes."""
    from mathutils.bvhtree import BVHTree
    verts, faces = [], []
    for nm, ob in panels.items():
        me = ob.data
        off = len(verts)
        verts += [v.co.copy() for v in me.vertices]
        faces += [[off + i for i in p.vertices] for p in me.polygons]
    return BVHTree.FromPolygons(verts, faces, all_triangles=False), verts, faces


def _side_point(x, z, s=1):
    """Point on the white side surface at (x, z) (left side if s>0), slightly proud."""
    half, tags = profile_at(x)
    pts = [p for p, t in zip(half, tags) if t in ('D', 'R')]
    zs = [float(p[1]) for p in pts]
    ys = [float(p[0]) for p in pts]
    order = np.argsort(zs)
    y = float(np.interp(z, np.array(zs)[order], np.array(ys)[order]))
    return Vector((x, s * y, z))


def build_details(col, mats, panels=None):
    """Black blade behind each front wheel with the amber marker at its rear end (parented to the fender so it follows
    the bullet-time peel), small red markers on the rear quarters."""
    objs = []
    for s in (1, -1):
        bm = bmesh.new()
        ba = bmesh.new()
        xs_ = np.linspace(0.80, 1.05, 14)
        top, bot = [], []
        for x in xs_:
            t = (x - 0.80) / 0.25
            zc = 0.745 + 0.02 * t
            h = 0.034 * (1 - 0.65 * t)
            top.append(_side_point(x, zc + h / 2, s) + Vector((0, s * 0.0015, 0)))
            bot.append(_side_point(x, zc - h / 2, s) + Vector((0, s * 0.0015, 0)))
        vt = [bm.verts.new(p) for p in top]
        vb = [bm.verts.new(p) for p in bot]
        for k in range(len(vt) - 1):
            q = (vt[k], vb[k], vb[k + 1], vt[k + 1])
            bm.faces.new(q if s > 0 else q[::-1])
        ob = L.bm_obj('RS2_blade_' + ('L' if s > 0 else 'R'), bm, col, smooth=True, mat=mats['gloss_black'])
        sol = ob.modifiers.new('t', 'SOLIDIFY')
        sol.thickness = 0.004
        sol.offset = 1.0
        pa = _side_point(0.835, 0.745, s) + Vector((0, s * 0.004, 0))
        L.bm_box(ba, pa, (0.040, 0.006, 0.010))
        am = L.bm_obj('RS2_marker_' + ('L' if s > 0 else 'R'), ba, col, mat=mats['amber'])
        L.parent_keep_local(am, ob)
        fen = (panels or {}).get('fender_' + ('L' if s > 0 else 'R'))
        if fen is not None:
            L.parent_keep_local(ob, fen)
        objs.append(ob)
        # rear red marker on the quarter, low behind the rear wheel
        br = bmesh.new()
        pr = _side_point(-1.96, 0.56, s) + Vector((0, s * 0.003, 0))
        L.bm_box(br, pr, (0.030, 0.006, 0.010))
        rm = L.bm_obj('RS2_rearmarker_' + ('L' if s > 0 else 'R'), br, col, mat=mats['taillight'])
        q = (panels or {}).get('quarter_' + ('L' if s > 0 else 'R'))
        if q is not None:
            L.parent_keep_local(rm, q)
        objs.append(rm)
    return objs
