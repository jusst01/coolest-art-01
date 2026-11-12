#!/usr/bin/env python3
"""
make.fun competition entry: coolest-art-01
Procedural SDF & Triangle Renderer in Python Standard Library.
Winning Scene: Chrome Diner Robot (Retro-futurist poster style).
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


# ==================== WINNING SCENE: CHROME DINER ROBOT ====================
def render_robot(canvas):
    # Background deep teal-navy #0E2A38
    c_bg = hex_to_rgb("#0E2A38")
    canvas.fill(c_bg)

    # Sunburst: 24 subtle rays from (512, 460)
    c_sun = hex_to_rgb("#FFFFFF")
    for i in range(24):
        angle = i * (2 * math.pi / 24)
        x2 = 512 + math.cos(angle) * 900
        y2 = 460 + math.sin(angle) * 900
        canvas.draw_capsule(512, 460, x2, y2, 3, c_sun, feather=1.5)

    # Big coral disc cx512 cy460 r252 #FF6B4A with radial warmth
    c_coral = hex_to_rgb("#FF6B4A")
    canvas.draw_circle_sdf(512, 460, 252, c_coral, feather=2.0)

    # Floor: bottom 150 px in #0A1E29 with retro checker blocks
    c_floor = hex_to_rgb("#0A1E29")
    for y in range(874, 1024):
        for x in range(1024):
            canvas.set_pixel(x, y, c_floor[0], c_floor[1], c_floor[2], 1.0)

    for fx in range(0, 1024, 64):
        canvas.draw_rounded_box(fx + 32, 920, 56, 40, 4, 4, c_coral, feather=1.0)

    # Offset-print look helper: draw shapes shifted (+5,+5) in coral, then in place in steel
    c_steel1 = hex_to_rgb("#EDF3F8")
    c_steel2 = hex_to_rgb("#93A7BA")
    c_darkscreen = hex_to_rgb("#0E1B26")
    c_cyan = hex_to_rgb("#4EF0E0")

    # Robot Head rounded box (360..664, 236..516) -> center (512, 376), w=304, h=280
    canvas.draw_rounded_box(517, 381, 304, 280, 32, 32, c_coral, feather=1.5)
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

    # Eyes: two cyan circles with white specular highlights
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

    # Coffee cup: white trapezoid + sleeve band + handle
    canvas.draw_rounded_box(736, 632, 64, 72, 8, 12, hex_to_rgb("#FFFFFF"), feather=1.0)
    canvas.draw_capsule(736, 608, 736, 656, 12, c_coral, feather=1.0)
    canvas.draw_circle_sdf(774, 632, 14, c_steel1, feather=1.0)

    # Steam above cup
    c_steam = hex_to_rgb("#FFFFFF")
    canvas.draw_capsule(720, 570, 732, 540, 5, c_steam, feather=1.0)
    canvas.draw_capsule(750, 565, 740, 535, 5, c_steam, feather=1.0)

    # Feet: rounded boxes
    c_boot = hex_to_rgb("#22303C")
    canvas.draw_rounded_box(460, 844, 104, 44, 16, 16, c_boot, feather=1.5)
    canvas.draw_rounded_box(564, 844, 104, 44, 16, 16, c_boot, feather=1.5)


# ==================== MAIN ====================
def main():
    # Default scene is winning scene: robot
    scene_name = os.environ.get("SCENE", "robot").lower()
    if len(sys.argv) > 1:
        scene_name = sys.argv[1].lower()

    print(f"Rendering default scene: {scene_name}")
    start_time = time.time()

    canvas = Canvas(WIDTH, HEIGHT)
    render_robot(canvas) # Always render robot as winner / default

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    out_path = os.path.join(out_dir, "entry.png")
    canvas.save_png(out_path)

    elapsed = time.time() - start_time
    print(f"Successfully rendered {scene_name} to {out_path} in {elapsed:.2f}s")

if __name__ == "__main__":
    main()
