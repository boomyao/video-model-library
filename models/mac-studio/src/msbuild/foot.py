import math
import numpy as np
from . import dims as D
from .util import MM, mesh_np, obj, recalc_normals, points_mesh, fillet_polyline, revolve_profile, add_smooth_mod
from .plan import PlanLoop
from .gn import holes_boolean_group

R_JOIN = 92.0


def outer_profile():
    a = math.radians(D.FOOT_SLOPE_DEG)
    r_fc = D.FOOT_R_TOP - (D.Z_PB - D.FOOT_Z_FLAT) / math.tan(a)
    gz = D.FOOT_Z_FLAT + D.RING_GROOVE_DEPTH
    ro = D.RING_R_OUT + 0.15
    ri = D.RING_R_IN - 0.15
    pts = [(R_JOIN, D.Z_PB), (D.FOOT_R_TOP, D.Z_PB), (r_fc, D.FOOT_Z_FLAT), (ro, D.FOOT_Z_FLAT),
           (ro, gz), (ri, gz), (ri, D.FOOT_Z_FLAT), (0.0, D.FOOT_Z_FLAT)]
    radii = [0, D.FOOT_CONCAVE_R, D.FOOT_CONVEX_R, 0.12, 0.1, 0.1, 0.12, 0]
    return fillet_polyline(pts, radii, arc_seg=10)


def inner_profile():
    a = math.radians(D.FOOT_SLOPE_DEG)
    t = D.FOOT_BAND_T
    px = D.FOOT_R_TOP - t * math.sin(a)
    pz = D.Z_PB + t * math.cos(a)
    z_cf = D.FOOT_Z_FLAT + D.RING_GROOVE_DEPTH + 1.3
    r_open = px + (D.Z_PT - pz) / math.tan(a)
    r_cf = px - (pz - z_cf) / math.tan(a)
    pts = [(0.0, z_cf), (r_cf, z_cf), (r_open, D.Z_PT), (R_JOIN, D.Z_PT)]
    radii = [0, 1.6, 0.4, 0]
    return fillet_polyline(pts, radii, arc_seg=8), z_cf


def build_cover_mesh(segments=1024, name='Bottom_Cover'):
    plan = PlanLoop()
    ang = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ca, sa = np.cos(ang), np.sin(ang)
    inner, z_cf = inner_profile()
    outer = outer_profile()
    ch = 0.3
    dpl = D.WALL_T + D.PLATE_GAP
    r_a = plan.offset_polar(dpl + ch, ang)
    r_b = plan.offset_polar(dpl, ang)
    rings = []
    rings.append(('pole', np.array([0.0, 0.0, inner[0][1]])))
    for r, z in inner[1:]:
        rings.append(('ring', np.column_stack([r * ca, r * sa, np.full(segments, z)])))
    rings.append(('ring', np.column_stack([r_a * ca, r_a * sa, np.full(segments, D.Z_PT)])))
    rings.append(('ring', np.column_stack([r_b * ca, r_b * sa, np.full(segments, D.Z_PT - ch)])))
    rings.append(('ring', np.column_stack([r_b * ca, r_b * sa, np.full(segments, D.Z_PB + ch)])))
    rings.append(('ring', np.column_stack([r_a * ca, r_a * sa, np.full(segments, D.Z_PB)])))
    for r, z in outer[:-1]:
        rings.append(('ring', np.column_stack([r * ca, r * sa, np.full(segments, z)])))
    rings.append(('pole', np.array([0.0, 0.0, outer[-1][1]])))
    verts = []
    starts = []
    idx = 0
    for kind, v in rings:
        starts.append(idx)
        v = np.atleast_2d(v)
        verts.append(v)
        idx += len(v)
    faces = []
    for j in range(len(rings) - 1):
        ka, ia = rings[j][0], starts[j]
        kb, ib = rings[j + 1][0], starts[j + 1]
        for i in range(segments):
            i2 = (i + 1) % segments
            if ka == 'ring' and kb == 'ring':
                faces.append((ia + i, ia + i2, ib + i2, ib + i))
            elif ka == 'pole':
                faces.append((ia, ib + i2, ib + i))
            else:
                faces.append((ia + i, ia + i2, ib))
    me = mesh_np(name, np.vstack(verts) * MM, faces)
    recalc_normals(me)
    return me


def hole_points():
    a = math.radians(D.FOOT_SLOPE_DEG)
    e = math.radians(D.FOOT_HOLE_ELEV_DEG)
    psi = math.radians(D.FOOT_HOLE_SWIRL_DEG)
    n = D.FOOT_HOLES_PER_ROW
    pts = []
    dirs = []
    for k in range(D.FOOT_HOLE_ROWS):
        s = D.FOOT_ROW_S0 + k * D.FOOT_ROW_PITCH
        r = D.FOOT_R_TOP - s * math.cos(a)
        z = D.Z_PB - s * math.sin(a)
        phi = (np.arange(n) + 0.5 * (k % 2)) * 2 * np.pi / n
        cp, sp = np.cos(phi), np.sin(phi)
        P = np.column_stack([r * cp, r * sp, np.full(n, z)])
        dr = -math.cos(e) * math.cos(psi)
        dt = math.cos(e) * math.sin(psi)
        dz = math.sin(e)
        Dv = np.column_stack([dr * cp - dt * sp, dr * sp + dt * cp, np.full(n, dz)])
        pts.append(P)
        dirs.append(Dv)
    return np.vstack(pts), np.vstack(dirs)


def ring_mesh(segments=512, name='Foot_Ring'):
    import bmesh
    ri, ro, t = D.RING_R_IN, D.RING_R_OUT, D.RING_T
    mid = ((ri + ro) / 2, 0.0)
    pts = [mid, (ro, 0.0), (ro, t), (ri, t), (ri, 0.0), mid]
    prof = list(fillet_polyline(pts, [0, 0.4, 0.12, 0.12, 0.4, 0], arc_seg=6)[:-1])
    v, f, rings = revolve_profile(prof + [prof[0]], segments)
    me = mesh_np(name, v * MM, f)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return me


def build(coll, mats, hole_segments=16):
    me = build_cover_mesh()
    cover = obj('Bottom_Cover', me, coll, mat=mats['al'])
    pts, dirs = hole_points()
    pm = points_mesh('PTS_FootHoles', pts * MM, {'dir': ('FLOAT_VECTOR', dirs)})
    po = obj('PTS_FootHoles', pm, coll)
    po.hide_render = True
    po.hide_viewport = True
    ng = holes_boolean_group('GN_Foot_Holes', po, mats['al_drill'], radius_mm=D.FOOT_HOLE_D / 2,
                             depth_mm=7.0, segments=hole_segments)
    mod = cover.modifiers.new('Angled_Holes', 'NODES')
    mod.node_group = ng
    cover['foot_holes'] = len(pts)
    cover['hole_elevation_deg'] = D.FOOT_HOLE_ELEV_DEG
    cover['hole_swirl_deg'] = D.FOOT_HOLE_SWIRL_DEG
    ring = obj('Foot_Ring', ring_mesh(), coll, mat=mats['rubber'])
    add_smooth_mod(ring, 40)
    return dict(cover=cover, ring=ring, pts=po)
