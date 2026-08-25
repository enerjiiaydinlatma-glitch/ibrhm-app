"""
Ajan basina kisilik formu (bkz. Sign Council Rundown, gorsel katman
karari: karakter/maskot degil, soyut geometrik kisilik). generate_avatars.py
ve generate_avatar_concepts.py bu modulu paylasir.
"""
import math


def draw_circle(draw, cx, cy, r, color):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)


def draw_triangle(draw, cx, cy, r, color):
    draw.regular_polygon((cx, cy, r), n_sides=3, rotation=0, fill=color)


def draw_hexagon(draw, cx, cy, r, color):
    draw.regular_polygon((cx, cy, r), n_sides=6, rotation=0, fill=color)


def draw_squircle(draw, cx, cy, r, color):
    draw.rounded_rectangle((cx - r, cy - r, cx + r, cy + r), radius=r * 0.55, fill=color)


def draw_spike(draw, cx, cy, r, color, points=9):
    pts = []
    for i in range(points * 2):
        angle = math.pi * i / points - math.pi / 2
        radius = r if i % 2 == 0 else r * 0.45
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(pts, fill=color)


SHAPE_FNS = {
    "circle": draw_circle,
    "triangle": draw_triangle,
    "hexagon": draw_hexagon,
    "squircle": draw_squircle,
    "spike": draw_spike,
}

# Bazi formlarin gorsel agirlik merkezi (cx, cy)'den kayar - monogram
# metnini buna gore hafifce asagi/yukari kaydiriyoruz.
SHAPE_TEXT_OFFSET_Y = {
    "circle": 0,
    "triangle": 16,
    "hexagon": 0,
    "squircle": 0,
    "spike": 0,
}
