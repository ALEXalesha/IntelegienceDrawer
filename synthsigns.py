import numpy as np
from PIL import Image, ImageDraw

# Signs that EMNIST/HASY lack or barely have. Drawn procedurally with jitter.
NAMES = ["+", "-", "=", "×", "÷", "(", ")", "[", "]", "<", ">"]
S = 112  # render at 4x then downscale to 28 for smooth strokes


def _draw_sign(name, rng):
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    w = int(rng.integers(6, 12))                 # stroke width at 4x scale
    cx, cy = (S // 2 + rng.integers(-8, 9, size=2)).tolist()
    half = int(rng.integers(int(S * 0.28), int(S * 0.40)))   # arm half-length
    vh = int(rng.integers(int(S * 0.30), int(S * 0.42)))     # vertical half for brackets
    tick = int(rng.integers(int(S * 0.08), int(S * 0.16)))   # bracket foot length

    if name == "-":
        d.line([(cx - half, cy), (cx + half, cy)], fill=255, width=w)
    elif name == "+":
        d.line([(cx - half, cy), (cx + half, cy)], fill=255, width=w)
        d.line([(cx, cy - half), (cx, cy + half)], fill=255, width=w)
    elif name == "=":
        gap = int(rng.integers(int(S * 0.10), int(S * 0.20)))
        d.line([(cx - half, cy - gap), (cx + half, cy - gap)], fill=255, width=w)
        d.line([(cx - half, cy + gap), (cx + half, cy + gap)], fill=255, width=w)
    elif name == "×":
        d.line([(cx - half, cy - half), (cx + half, cy + half)], fill=255, width=w)
        d.line([(cx - half, cy + half), (cx + half, cy - half)], fill=255, width=w)
    elif name == "÷":
        d.line([(cx - half, cy), (cx + half, cy)], fill=255, width=w)
        dot = max(4, w)
        off = int(rng.integers(int(S * 0.16), int(S * 0.24)))
        for dy in (-off, off):
            d.ellipse([cx - dot, cy + dy - dot, cx + dot, cy + dy + dot], fill=255)
    elif name in "()":
        bw = int(rng.integers(int(S * 0.22), int(S * 0.34)))   # arc bulge width
        box = [cx - bw, cy - vh, cx + bw, cy + vh]
        if name == "(":
            d.arc(box, 90, 270, fill=255, width=w)
        else:
            d.arc(box, 270, 90, fill=255, width=w)
    elif name in "[]":
        if name == "[":
            x = cx - int(S * 0.10)
            d.line([(x, cy - vh), (x, cy + vh)], fill=255, width=w)
            d.line([(x, cy - vh), (x + tick, cy - vh)], fill=255, width=w)
            d.line([(x, cy + vh), (x + tick, cy + vh)], fill=255, width=w)
        else:
            x = cx + int(S * 0.10)
            d.line([(x, cy - vh), (x, cy + vh)], fill=255, width=w)
            d.line([(x, cy - vh), (x - tick, cy - vh)], fill=255, width=w)
            d.line([(x, cy + vh), (x - tick, cy + vh)], fill=255, width=w)
    elif name in "<>":
        if name == "<":
            d.line([(cx + half, cy - vh), (cx - half, cy), (cx + half, cy + vh)],
                   fill=255, width=w, joint="curve")
        else:
            d.line([(cx - half, cy - vh), (cx + half, cy), (cx - half, cy + vh)],
                   fill=255, width=w, joint="curve")

    angle = rng.uniform(-12, 12)
    img = img.rotate(angle, resample=Image.BILINEAR, fillcolor=0)
    return np.asarray(img.resize((28, 28), Image.LANCZOS), dtype="float32") / 255.0


def make(per_class, seed=0):
    rng = np.random.default_rng(seed)
    imgs, labels = [], []
    for i, name in enumerate(NAMES):
        for _ in range(per_class):
            imgs.append(_draw_sign(name, rng))
        labels.append(np.full(per_class, i, dtype="int64"))
    return np.stack(imgs), np.concatenate(labels)
