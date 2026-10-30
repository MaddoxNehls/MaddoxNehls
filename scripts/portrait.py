"""One-off: turn a headshot into the ASCII portraits in data/. The photo itself is never committed.

Usage: python scripts/portrait.py path/to/photo.jpg
Needs: pillow, numpy, opencv-python
"""
import os, sys
from collections import deque
import numpy as np
import cv2
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAMP = " .:-=+*#%@"
CELL = 6.6 / 14.2  # character width / line height in the card
# Picked by Maddox: variant 9 on dark, variant 6 on light.
STYLES = {
    'dark':  dict(cols=72, box=(60, 100, 660, 900), clahe=False, gamma=1.0, invert=False),
    'light': dict(cols=64, box=(110, 90, 610, 760), clahe=True, gamma=1.4, invert=True),
}

def backdrop_mask(rgb):
    """Flood-fill the flat studio backdrop from the top and side edges."""
    a = rgb.astype(int); H, W, _ = a.shape; ref = a[5, 5]
    bg = np.zeros((H, W), bool)
    near = lambda y, x: np.abs(a[y, x] - ref).sum() < 60 and abs(a[y, x, 0] - a[y, x, 2]) < 14
    q = deque([(0, x) for x in range(W)] + [(y, 0) for y in range(H * 2 // 3)] + [(y, W - 1) for y in range(H * 2 // 3)])
    while q:
        y, x = q.popleft()
        if 0 <= y < H and 0 <= x < W and not bg[y, x] and near(y, x):
            bg[y, x] = True
            q.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])
    return bg

def ascii_art(gray, bg, cols, box, clahe, gamma, invert):
    g = gray[box[1]:box[3], box[0]:box[2]]; m = bg[box[1]:box[3], box[0]:box[2]]
    if clahe: g = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(6, 6)).apply(g)
    a = g.astype(float) / 255
    lo, hi = np.percentile(a[~m], 3), np.percentile(a[~m], 99.5)
    L = np.clip((a - lo) / (hi - lo), 0, 1) ** gamma
    if invert: L = 1 - L
    h, w = L.shape; rows = round(cols * (h / w) * CELL)
    out = []
    for r in range(rows):
        y0, y1 = r * h // rows, (r + 1) * h // rows
        line = ''
        for c in range(cols):
            x0, x1 = c * w // cols, (c + 1) * w // cols
            keep = ~m[y0:y1, x0:x1]
            if keep.mean() < 0.4: line += ' '; continue
            d = max(0.06, min(1, L[y0:y1, x0:x1][keep].mean()))
            line += RAMP[min(len(RAMP) - 1, int(d * len(RAMP)))]
        out.append(line.rstrip())
    return out

if __name__ == '__main__':
    img = Image.open(sys.argv[1]).convert('RGB').resize((720, 960))
    rgb = np.asarray(img); gray = np.asarray(img.convert('L')); bg = backdrop_mask(rgb)
    for mode, style in STYLES.items():
        with open(os.path.join(ROOT, 'data', f'portrait-{mode}.txt'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(ascii_art(gray, bg, **style)) + '\n')
    print('wrote data/portrait-dark.txt and data/portrait-light.txt')
