#!/usr/bin/env python3
"""
make.fun competition entry: coolest-art-01
Procedural SDF & Triangle Renderer in Python Standard Library.
Scenes: fox (Stained-glass fox), robot (Chrome diner robot), landscape (Ringed planet).
"""

import math
import os
import struct
import sys
import time
import zlib

WIDTH = 1024
HEIGHT = 1024

class PRNG:
    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFF

    def random(self):
        self.s = (self.s + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.s
        t = (t ^ (t >> 15)) * (t | 1) & 0xFFFFFFFF
        t ^= t + ((t ^ (t >> 7)) * (t | 1) & 0xFFFFFFFF)
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def uniform(self, a, b):
        return a + (b - a) * self.random()

    def randint(self, a, b):
        return a + int(self.random() * (b - a + 1))

def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else (hi if v > hi else v)

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

class Canvas:
    def __init__(self, w=WIDTH, h=HEIGHT):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)

    def fill(self, color):
        r, g, b = color
        for i in range(0, len(self.buf), 3):
            self.buf[i] = r
            self.buf[i+1] = g
            self.buf[i+2] = b

    def set_pixel(self, x, y, r, g, b, a=1.0):
        if x < 0 or x >= self.w or y < 0 or y >= self.h:
            return
        if a <= 0.0:
            return
        idx = (y * self.w + x) * 3
        if a >= 1.0:
            self.buf[idx] = int(clamp(r, 0, 255))
            self.buf[idx+1] = int(clamp(g, 0, 255))
            self.buf[idx+2] = int(clamp(b, 0, 255))
        else:
            dr = self.buf[idx]
            dg = self.buf[idx+1]
            db = self.buf[idx+2]
            self.buf[idx] = int(clamp(r * a + dr * (1 - a), 0, 255))
            self.buf[idx+1] = int(clamp(g * a + dg * (1 - a), 0, 255))
            self.buf[idx+2] = int(clamp(b * a + db * (1 - a), 0, 255))

    def vertical_gradient(self, c_top, c_bottom):
        rt, gt, bt = c_top
        rb, gb, bb = c_bottom
        for y in range(self.h):
            f = y / (self.h - 1) if self.h > 1 else 0.0
            r = int(rt * (1 - f) + rb * f)
            g = int(gt * (1 - f) + gb * f)
            b = int(bt * (1 - f) + bb * f)
            row_start = y * self.w * 3
            for x in range(self.w):
                idx = row_start + x * 3
                self.buf[idx] = r
                self.buf[idx+1] = g
                self.buf[idx+2] = b

    def draw_circle_sdf(self, cx, cy, r, fill_color, feather=1.0):
        fr, fg, fb = fill_color
        xmin = max(0, int(cx - r - feather - 2))
        xmax = min(self.w, int(cx + r + feather + 2))
        ymin = max(0, int(cy - r - feather - 2))
        ymax = min(self.h, int(cy + r + feather + 2))
        for y in range(ymin, ymax):
            dy = y - cy
            for x in range(xmin, xmax):
                dx = x - cx
                dist = math.hypot(dx, dy) - r
                alpha = clamp(0.5 - dist / feather, 0.0, 1.0)
                if alpha > 0:
                    self.set_pixel(x, y, fr, fg, fb, alpha)

    def draw_radial_gradient_circle(self, cx, cy, r, c_inner, c_outer, feather=1.5):
        ri, gi, bi = c_inner
        ro, go, bo = c_outer
        xmin = max(0, int(cx - r - feather - 2))
        xmax = min(self.w, int(cx + r + feather + 2))
        ymin = max(0, int(cy - r - feather - 2))
        ymax = min(self.h, int(cy + r + feather + 2))
        for y in range(ymin, ymax):
            dy = y - cy
            for x in range(xmin, xmax):
                dx = x - cx
                dist = math.hypot(dx, dy)
                if dist > r + feather:
                    continue
                t = clamp(dist / r, 0.0, 1.0)
                cr = ri * (1 - t) + ro * t
                cg = gi * (1 - t) + go * t
                cb = bi * (1 - t) + bo * t
                alpha = clamp(0.5 - (dist - r) / feather, 0.0, 1.0)
                if alpha > 0:
                    self.set_pixel(x, y, cr, cg, cb, alpha)

    def draw_rounded_box(self, bx, by, bw, bh, rx, ry, fill_color, feather=1.0):
        fr, fg, fb = fill_color
        half_w = bw / 2.0
        half_h = bh / 2.0
        xmin = max(0, int(bx - half_w - feather - 2))
        xmax = min(self.w, int(bx + half_w + feather + 2))
        ymin = max(0, int(by - half_h - feather - 2))
        ymax = min(self.h, int(by + half_h + feather + 2))
        for y in range(ymin, ymax):
            py = y - by
            for x in range(xmin, xmax):
                px = x - bx
                dx = abs(px) - half_w + rx
                dy = abs(py) - half_h + ry
                outside = math.hypot(max(dx, 0.0), max(dy, 0.0))
                inside = min(max(dx, dy), 0.0)
                dist = outside + inside - min(rx, ry)
                alpha = clamp(0.5 - dist / feather, 0.0, 1.0)
                if alpha > 0:
                    self.set_pixel(x, y, fr, fg, fb, alpha)

    def draw_capsule(self, x1, y1, x2, y2, r, fill_color, feather=1.0):
        fr, fg, fb = fill_color
        min_x = int(min(x1, x2) - r - feather - 2)
        max_x = int(max(x1, x2) + r + feather + 2)
        min_y = int(min(y1, y2) - r - feather - 2)
        max_y = int(max(y1, y2) + r + feather + 2)
        xmin = max(0, min_x)
        xmax = min(self.w, max_x)
        ymin = max(0, min_y)
        ymax = min(self.h, max_y)

        ba_x = x2 - x1
        ba_y = y2 - y1
        ba_len_sq = ba_x*ba_x + ba_y*ba_y

        for y in range(ymin, ymax):
            for x in range(xmin, xmax):
                pa_x = x - x1
                pa_y = y - y1
                if ba_len_sq == 0:
                    h = 0.0
                else:
                    h = clamp((pa_x * ba_x + pa_y * ba_y) / ba_len_sq, 0.0, 1.0)
                dx = pa_x - h * ba_x
                dy = pa_y - h * ba_y
                dist = math.hypot(dx, dy) - r
                alpha = clamp(0.5 - dist / feather, 0.0, 1.0)
                if alpha > 0:
                    self.set_pixel(x, y, fr, fg, fb, alpha)

    def draw_triangle(self, p0, p1, p2, fill_color, shrink=1.0, feather=1.0):
        fr, fg, fb = fill_color
        # Centroid
        cx = (p0[0] + p1[0] + p2[0]) / 3.0
        cy = (p0[1] + p1[1] + p2[1]) / 3.0

        # Shrink toward centroid
        def shrink_pt(p):
            return (cx + (p[0] - cx) * shrink, cy + (p[1] - cy) * shrink)

        tp0 = shrink_pt(p0)
        tp1 = shrink_pt(p1)
        tp2 = shrink_pt(p2)

        xmin = max(0, int(min(tp0[0], tp1[0], tp2[0]) - feather - 1))
        xmax = min(self.w, int(max(tp0[0], tp1[0], tp2[0]) + feather + 2))
        ymin = max(0, int(min(tp0[1], tp1[1], tp2[1]) - feather - 1))
        ymax = min(self.h, int(max(tp0[1], tp1[1], tp2[1]) + feather + 2))

        x0, y0 = tp0
        x1, y1 = tp1
        x2, y2 = tp2

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-5:
            return

        for y in range(ymin, ymax):
            for x in range(xmin, xmax):
                w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / denom
                w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / denom
                w2 = 1.0 - w0 - w1
                if w0 >= -0.05 and w1 >= -0.05 and w2 >= -0.05:
                    # distance approximation for anti-aliasing
                    min_w = min(w0, w1, w2)
                    # convert barycentric min_w roughly to pixel distance or use standard alpha
                    alpha = clamp(min_w * 15.0, 0.0, 1.0) # feather edge
                    if alpha > 0:
                        self.set_pixel(x, y, fr, fg, fb, alpha)

    def save_png(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0) # filter type 0 (None)
            row_start = y * stride
            raw.extend(self.buf[row_start:row_start + stride])

        compressed = zlib.compress(raw, level=9)

        def chunk(tag, data):
            return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', 0xFFFFFFFF & zlib.crc32(tag + data))

        png = bytearray(b'\x89PNG\r\n\x1a\n')
        ihdr = struct.pack('>IIBBBBB', self.w, self.h, 8, 2, 0, 0, 0)
        png.extend(chunk(b'IHDR', ihdr))
        png.extend(chunk(b'IDAT', compressed))
        png.extend(chunk(b'IEND', b''))

        with open(path, 'wb') as f:
            f.write(png)

# ==================== SCENE A: STAINED GLASS FOX ====================
def render_fox(canvas):
    # Background vertical gradient: deep indigo #131040 -> near-black #05060F
    c_indigo = hex_to_rgb("#131040")
    c_nearblack = hex_to_rgb("#05060F")
    canvas.vertical_gradient(c_indigo, c_nearblack)

    # Golden disc behind head: circle cx512 cy480 r305, radial gradient #FFD98A -> #E8930C
    c_gold1 = hex_to_rgb("#FFD98A")
    c_gold2 = hex_to_rgb("#E8930C")
    canvas.draw_radial_gradient_circle(512, 480, 305, c_gold1, c_gold2, feather=6.0)

    # Fox head outline / silhouette & facets
    # We can rasterize stained glass triangles inside the head silhouette.
    prng = PRNG(7)
    jewel_hexes = ["#F59E0B", "#DC2626", "#0D9488", "#2563EB", "#7C3AED", "#FACC15", "#EA580C"]
    jewels = [hex_to_rgb(h) for h in jewel_hexes]

    # Generate grid quads split into triangles across head bounding box
    step = 62
    jitter_range = 21

    # Simple helper to check if a point is roughly inside fox head silhouette
    def is_in_fox(px, py):
        # cheeks circle cx512 cy545 r238
        d_cheeks = math.hypot(px - 512, py - 545) - 238
        # muzzle polygon approx or bounding
        d_muzzle = 9999
        if 628 <= py <= 806:
            # trapezoid bounds
            t = (py - 628) / (806 - 628)
            x_left = 408 + (476 - 408) * t
            x_right = 616 + (546 - 616) * t
            if x_left <= px <= x_right:
                d_muzzle = 0
        # ears polygons roughly
        d_ears = 9999
        # left ear (292,380),(388,108),(478,322)
        # right ear (732,380),(636,108),(546,322)
        return d_cheeks <= 0 or d_muzzle <= 0 or d_ears <= 0 # refined below via triangle centroid check

    # Build facet grid
    for gy in range(150, 850, step):
        for gx in range(250, 774, step):
            jx1 = gx + prng.uniform(-jitter_range, jitter_range)
            jy1 = gy + prng.uniform(-jitter_range, jitter_range)
            jx2 = gx + step + prng.uniform(-jitter_range, jitter_range)
            jy2 = gy + prng.uniform(-jitter_range, jitter_range)
            jx3 = gx + step + prng.uniform(-jitter_range, jitter_range)
            jy3 = gy + step + prng.uniform(-jitter_range, jitter_range)
            jx4 = gx + prng.uniform(-jitter_range, jitter_range)
            jy4 = gy + step + prng.uniform(-jitter_range, jitter_range)

            # Split quad into two triangles
            tri1 = ((jx1, jy1), (jx2, jy2), (jx3, jy3))
            tri2 = ((jx1, jy1), (jx3, jy3), (jx4, jy4))

            for tri in [tri1, tri2]:
                cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3.0
                cy = (tri[0][1] + tri[1][1] + tri[2][1]) / 3.0

                # Check if centroid is inside head region
                # Cheeks circle r238 at (512, 545)
                d_head = math.hypot(cx - 512, cy - 545)
                # Ears check
                in_left_ear = (cx >= 280 and cx <= 490 and cy >= 100 and cy <= 400 and (cy - 380) <= -1.4 * abs(cx - 385))
                in_right_ear = (cx >= 530 and cx <= 740 and cy >= 100 and cy <= 400 and (cy - 380) <= -1.4 * abs(cx - 639))
                in_muzzle = (cx >= 400 and cx <= 620 and cy >= 620 and cy <= 810)

                if d_head <= 245 or in_left_ear or in_right_ear or in_muzzle:
                    # Pick jewel color based on hash of centroid
                    color_idx = int(abs(cx * 73 + cy * 31)) % len(jewels)
                    base_color = jewels[color_idx]

                    # Brighten toward disc center (512, 480)
                    dist_disc = math.hypot(cx - 512, cy - 480)
                    factor = clamp(0.75 + 0.45 * (1.0 - dist_disc / 700.0), 0.5, 1.4)
                    col = (
                        int(clamp(base_color[0] * factor, 0, 255)),
                        int(clamp(base_color[1] * factor, 0, 255)),
                        int(clamp(base_color[2] * factor, 0, 255))
                    )
                    canvas.draw_triangle(tri[0], tri[1], tri[2], col, shrink=0.90, feather=1.2)

    # Inner ears: pale rose facets
    c_rose = hex_to_rgb("#F5C6D6")
    canvas.draw_triangle((340, 320), (388, 140), (430, 300), c_rose, shrink=0.88, feather=1.2)
    canvas.draw_triangle((684, 320), (636, 140), (594, 300), c_rose, shrink=0.88, feather=1.2)

    # Eyes: almond polygons / capsules
    c_eye = hex_to_rgb("#FFE066")
    c_pupil = hex_to_rgb("#0B0714")
    canvas.draw_circle_sdf(414, 512, 32, c_eye, feather=1.5)
    canvas.draw_circle_sdf(610, 512, 32, c_eye, feather=1.5)
    canvas.draw_capsule(414, 492, 414, 532, 6, c_pupil, feather=1.0)
    canvas.draw_capsule(610, 492, 610, 532, 6, c_pupil, feather=1.0)

    # Nose: rounded triangle at (512, 772) solid #0B0714
    canvas.draw_triangle((512, 740), (480, 790), (544, 790), c_pupil, shrink=0.9, feather=1.0)

    # Sparkles around head (5 small white 4-point stars)
    c_white = hex_to_rgb("#FFFFFF")
    for sx, sy in [(200, 300), (820, 260), (512, 120), (180, 600), (840, 620)]:
        canvas.draw_circle_sdf(sx, sy, 5, c_white, feather=1.0)
        canvas.draw_capsule(sx - 10, sy, sx + 10, sy, 2, c_white, feather=1.0)
        canvas.draw_capsule(sx, sy - 10, sx, sy + 10, 2, c_white, feather=1.0)


# ==================== SCENE B: CHROME DINER ROBOT ====================
def render_robot(canvas):
    # Background deep teal-navy #0E2A38
    c_bg = hex_to_rgb("#0E2A38")
    canvas.fill(c_bg)

    # Sunburst: 24 wedges from (512, 460)
    c_sun = hex_to_rgb("#FFFFFF")
    for i in range(24):
        angle = i * (2 * math.pi / 24)
        x2 = 512 + math.cos(angle) * 800
        y2 = 460 + math.sin(angle) * 800
        canvas.draw_capsule(512, 460, x2, y2, 4, c_sun, feather=1.5) # alpha handled via low color or blending if needed, let's draw subtle wedges

    # Big coral disc cx512 cy460 r252 #FF6B4A
    c_coral = hex_to_rgb("#FF6B4A")
    canvas.draw_circle_sdf(512, 460, 252, c_coral, feather=2.0)

    # Floor: bottom 150 px in #0A1E29 with perspective checker strip
    c_floor = hex_to_rgb("#0A1E29")
    for y in range(874, 1024):
        for x in range(1024):
            canvas.set_pixel(x, y, c_floor[0], c_floor[1], c_floor[2], 1.0)

    c_cream = hex_to_rgb("#FFF3E4")
    # Checker strip on floor
    for fx in range(0, 1024, 64):
        canvas.draw_rounded_box(fx + 32, 920, 56, 40, 4, 4, c_coral, feather=1.0)

    # Offset-print look helper: draw shapes shifted (+5,+5) in coral, then in place in steel
    c_steel1 = hex_to_rgb("#EDF3F8")
    c_steel2 = hex_to_rgb("#93A7BA")
    c_darkscreen = hex_to_rgb("#0E1B26")
    c_cyan = hex_to_rgb("#4EF0E0")

    # Robot Head rounded box (360..664, 236..516) -> center (512, 376), w=304, h=280
    # Offset shadow/print layer
    canvas.draw_rounded_box(517, 381, 304, 280, 32, 32, c_coral, feather=1.5)
    # Main head
    canvas.draw_rounded_box(512, 376, 304, 280, 32, 32, c_steel1, feather=1.5)

    # Antenna
    canvas.draw_capsule(512, 236, 512, 178, 8, c_steel2, feather=1.0)
    canvas.draw_circle_sdf(512, 178, 21, c_coral, feather=1.5)
    canvas.draw_circle_sdf(506, 172, 6, hex_to_rgb("#FFFFFF"), feather=1.0)

    # Ear discs
    canvas.draw_circle_sdf(352, 392, 26, c_coral, feather=1.5)
    canvas.draw_circle_sdf(352, 392, 16, c_steel1, feather=1.0)
    canvas.draw_circle_sdf(672, 392, 26, c_coral, feather=1.5)
    canvas.draw_circle_sdf(672, 392, 16, c_steel1, feather=1.0)

    # Face screen rounded box (392..632, 288..468) -> center (512, 378), w=240, h=180
    canvas.draw_rounded_box(512, 378, 240, 180, 20, 20, c_darkscreen, feather=1.0)

    # Eyes: two cyan capsules / circles
    canvas.draw_circle_sdf(475, 360, 22, c_cyan, feather=1.0)
    canvas.draw_circle_sdf(549, 360, 22, c_cyan, feather=1.0)
    canvas.draw_circle_sdf(468, 353, 6, hex_to_rgb("#FFFFFF"), feather=1.0)
    canvas.draw_circle_sdf(542, 353, 6, hex_to_rgb("#FFFFFF"), feather=1.0)

    # Mouth grille: 5 small vertical rounded bars around y 425
    for mx in range(460, 565, 26):
        canvas.draw_capsule(mx, 410, mx, 440, 5, c_cyan, feather=1.0)

    # Body rounded box (398..626, 548..822) -> center (512, 685), w=228, h=274
    canvas.draw_rounded_box(517, 690, 228, 274, 28, 28, c_coral, feather=1.5)
    canvas.draw_rounded_box(512, 685, 228, 274, 28, 28, c_steel2, feather=1.5)

    # Chest panel rounded box (446..578, 600..716) -> center (512, 658), w=132, h=116
    canvas.draw_rounded_box(512, 658, 132, 116, 14, 14, c_darkscreen, feather=1.0)
    canvas.draw_circle_sdf(480, 658, 10, c_coral, feather=1.0)
    canvas.draw_circle_sdf(512, 658, 10, c_cyan, feather=1.0)
    canvas.draw_circle_sdf(544, 658, 10, hex_to_rgb("#FACC15"), feather=1.0)

    # Belt line
    canvas.draw_capsule(410, 780, 614, 780, 8, c_darkscreen, feather=1.0)

    # Arms: left hanging, right raised holding coffee cup
    canvas.draw_capsule(398, 580, 352, 742, 26, c_steel1, feather=1.5)
    canvas.draw_capsule(626, 580, 724, 668, 26, c_steel1, feather=1.5)

    # Coffee cup: white trapezoid (700..772, 596..668) + handle
    canvas.draw_rounded_box(736, 632, 64, 72, 8, 12, hex_to_rgb("#FFFFFF"), feather=1.0)
    canvas.draw_capsule(736, 608, 736, 656, 12, c_coral, feather=1.0) # sleeve band
    canvas.draw_circle_sdf(774, 632, 14, c_steel1, feather=1.0) # handle arc

    # Steam above cup
    c_steam = hex_to_rgb("#FFFFFF")
    canvas.draw_capsule(720, 570, 732, 540, 5, c_steam, feather=1.0)
    canvas.draw_capsule(750, 565, 740, 535, 5, c_steam, feather=1.0)

    # Feet: rounded boxes (408..512, 822..866) and (512..616, 822..866)
    c_boot = hex_to_rgb("#22303C")
    canvas.draw_rounded_box(460, 844, 104, 44, 16, 16, c_boot, feather=1.5)
    canvas.draw_rounded_box(564, 844, 104, 44, 16, 16, c_boot, feather=1.5)


# ==================== SCENE C: RINGED PLANET LANDSCAPE ====================
def render_landscape(canvas):
    # Sky vertical gradient: #150A33 -> #45135E -> horizon glow #C73E5E at y~700
    c_sky1 = hex_to_rgb("#150A33")
    c_sky2 = hex_to_rgb("#45135E")
    c_glow = hex_to_rgb("#C73E5E")

    for y in range(HEIGHT):
        f = y / HEIGHT
        if f < 0.7:
            t = f / 0.7
            r = int(c_sky1[0] * (1 - t) + c_sky2[0] * t)
            g = int(c_sky1[1] * (1 - t) + c_sky2[1] * t)
            b = int(c_sky1[2] * (1 - t) + c_sky2[2] * t)
        else:
            t = (f - 0.7) / 0.3
            r = int(c_sky2[0] * (1 - t) + c_glow[0] * t)
            g = int(c_sky2[1] * (1 - t) + c_glow[1] * t)
            b = int(c_sky2[2] * (1 - t) + c_glow[2] * t)
        row_start = y * WIDTH * 3
        for x in range(WIDTH):
            idx = row_start + x * 3
            canvas.buf[idx] = r
            canvas.buf[idx+1] = g
            canvas.buf[idx+2] = b

    # Stars: ~260 PRNG dots (seed 11), white, above y 640
    prng_stars = PRNG(11)
    c_white = hex_to_rgb("#FFFFFF")
    for _ in range(260):
        sx = prng_stars.randint(10, WIDTH - 10)
        sy = prng_stars.randint(10, 630)
        sz = prng_stars.randint(1, 3)
        canvas.draw_circle_sdf(sx, sy, sz, c_white, feather=0.8)

    # Crescent moon small at (168, 150) r34 cream
    c_moon = hex_to_rgb("#FFF9E6")
    canvas.draw_circle_sdf(168, 150, 34, c_moon, feather=1.0)
    canvas.draw_circle_sdf(180, 142, 30, hex_to_rgb("#1E0F3A"), feather=1.0) # shadow cut

    # Planet back ring (behind planet)
    # Ring ellipse cx668 cy318 rx302 ry60 rotated -16 deg
    c_ring = hex_to_rgb("#FFD9A0")
    # Draw ring segments where y <= cy or similar (back half)
    # For simplicity, draw full ring ellipse with alpha 0.7, then planet over it, then front ring over it.
    def draw_ring_half(front_flag):
        cx, cy = 668, 318
        rx, ry = 302, 60
        angle_rad = math.radians(-16)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        for theta in range(0, 360, 1):
            th = math.radians(theta)
            # Parametric ellipse in local space
            lx = rx * math.cos(th)
            ly = ry * math.sin(th)
            # Rotate and translate
            rx_pt = cx + lx * cos_a - ly * sin_a
            ry_pt = cy + lx * sin_a + ly * cos_a

            # Depth / front-back split: in planet space, is it in front or behind?
            # Actually, standard ring split: compare ly or world y relative to planet center
            is_front = (ly > 0)
            if is_front == front_flag:
                canvas.draw_circle_sdf(rx_pt, ry_pt, 8, c_ring, feather=1.2)

    draw_ring_half(False) # Back ring

    # Planet circle cx668 cy318 r148, vertical gradient #F7C873 -> #E2703A
    c_p1 = hex_to_rgb("#F7C873")
    c_p2 = hex_to_rgb("#E2703A")
    canvas.draw_radial_gradient_circle(668, 318, 148, c_p1, c_p2, feather=2.0)

    # Darker band arcs across planet
    c_band = hex_to_rgb("#C2542E")
    canvas.draw_capsule(540, 350, 796, 310, 18, c_band, feather=2.0)
    canvas.draw_capsule(530, 280, 770, 260, 12, c_band, feather=2.0)

    draw_ring_half(True) # Front ring

    # Mountains: three jagged polygon ridge layers (deterministic ridges via PRNG seed 5/6/7)
    # Layers from y~640 down to 1024
    mountain_layers = [
        (PRNG(5), hex_to_rgb("#2A1650"), 640, 780),
        (PRNG(6), hex_to_rgb("#1B0D36"), 720, 900),
        (PRNG(7), hex_to_rgb("#0F0620"), 820, 1024)
    ]

    for prng_m, col, y_base, y_bottom in mountain_layers:
        pts = [(0, HEIGHT)]
        curr_y = y_base
        for x in range(0, WIDTH + 60, 60):
            curr_y += prng_m.randint(-45, 45)
            curr_y = max(y_base - 80, min(y_bottom - 20, curr_y))
            pts.append((x, curr_y))
        pts.append((WIDTH, HEIGHT))

        # Rasterize mountain layer as polygons / triangles
        for i in range(1, len(pts) - 1):
            p0 = (pts[i-1][0], HEIGHT)
            p1 = pts[i-1]
            p2 = pts[i]
            canvas.draw_triangle(p0, p1, p2, col, shrink=1.0, feather=1.0)
            p3 = (pts[i][0], HEIGHT)
            canvas.draw_triangle(p1, p2, p3, col, shrink=1.0, feather=1.0)


# ==================== MAIN ====================
def main():
    scene_name = os.environ.get("SCENE", "fox").lower()
    if len(sys.argv) > 1:
        scene_name = sys.argv[1].lower()

    print(f"Rendering scene: {scene_name}")
    start_time = time.time()

    canvas = Canvas(WIDTH, HEIGHT)

    if scene_name == "fox":
        render_fox(canvas)
    elif scene_name == "robot":
        render_robot(canvas)
    elif scene_name == "landscape":
        render_landscape(canvas)
    else:
        print(f"Unknown scene '{scene_name}', defaulting to 'fox'")
        render_fox(canvas)

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    out_path = os.path.join(out_dir, "entry.png")
    canvas.save_png(out_path)

    elapsed = time.time() - start_time
    print(f"Successfully rendered {scene_name} to {out_path} in {elapsed:.2f}s")

if __name__ == "__main__":
    main()
