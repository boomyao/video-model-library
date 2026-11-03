"""The Force Touch module of the 12-inch MacBook (2015) on the dark stage, for the inside-the-machine shots.

    m = build_module()           # underside up: z = 0 is the plate's inner face, +z points into the laptop
    m.shift(0.12)                # the plate (glass, board, coils) moves x mm toward the rail (-y); the bracket stays
    m.current(1.0)               # coils lit violet (current flowing), 0..1
    light_module()               # house lighting for the module

Parts (see ft_scene.py for where every dimension comes from):
  m.plate    moving part: glass (z -1.33 .. -0.4), stiffener, sensor board, four coils on their teeth
  m.bracket  fixed part: H-shaped sheet with four spring tongues (the "beams"), strain gauges at their roots,
             gel pads at their tips, and the steel rail that the coils pull toward
Useful places, mm, underside up:
  coils: x ranges ft_scene.COILS, y 4.15 .. 11.05, z 0.2 .. 2.5; pole faces at y = 3.4
  rail:  x -26 .. 26, y 1.15 .. 2.95 (so the air gap between pole faces and rail is about 0.45 mm here; the film
         says "about 0.3 mm", which is the factory setting in Apple's patent, so shots that show the gap use gap=0.3)
  tongues (beams): centred x = +-43, roots at y = 20.3 / -17.5, tips at y = 31.0 / -28.2; gauges at the roots
"""
import math

import bpy
from mathutils import Vector

import ft_scene as S
import shotkit as K

MM = S.MM
TONGUES = {"NE": (43.0, 20.3, 31.0), "NW": (-43.0, 20.3, 31.0), "SE": (43.0, -17.5, -28.2), "SW": (-43.0, -17.5, -28.2)}


class Module:
    def __init__(self):
        self.M = None
        self.root = None
        self.plate = None
        self.bracket = None
        self._cur = None
        self.gap0 = 0.45

    def shift(self, mm):
        """Plate moves toward the rail (toward -y in the module's own frame)."""
        self.plate.location = (0, -mm * MM, 0)

    def current(self, k, color=K.VIOLET, strength=6.0):
        self._cur(strength * K.clamp(k), color)

    def flip(self, glass_up=True):
        self.root.rotation_euler = (0, math.pi if glass_up else 0.0, 0)


def build_module(gap=None, floor=True):
    m = Module()
    M = S.make_materials()
    m.M = M
    plate = S.build_plate(M)
    bracket = S.build_bracket(M)
    bracket.location = (0, 0, S.BRACKET_Z * MM)
    root = S.empty("MODULE")
    plate.parent = root
    bracket.parent = root
    m.root, m.plate, m.bracket = root, plate, bracket
    if gap is not None:                       # move the rail so that the air gap is `gap` mm
        rail = bpy.data.objects["rail"]
        rail.location.y += (m.gap0 - gap) * MM
        m.gap0 = gap
    m._cur = K.add_emission(M["copper"], K.VIOLET, 0.0)
    if floor:
        K.floor(z=-14.0)
    return m


def light_module(E=1.0, target=(2, 4, 4)):
    """Key from behind-left, cool rim from the right, warm kicker low on the left, soft top. Returns lamps by name."""
    L = {}
    L["key"] = K.area("key", (-120, 340, 400), target, 500, 4.0 * E, (1.0, 0.97, 0.93), size_y=200)
    L["rim"] = K.area("rim", (420, 260, 90), target, 340, 4.2 * E, (0.70, 0.83, 1.0), size_y=50)
    L["kick"] = K.area("kick", (-400, -100, 50), target, 240, 1.1 * E, (1.0, 0.76, 0.52), size_y=60)
    L["top"] = K.area("top", (0, -50, 600), target, 900, 0.9 * E, (0.9, 0.95, 1.0))
    return L
