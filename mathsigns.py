import csv
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HASY_DIR = os.path.join(HERE, "hasy")
CACHE = os.path.join(HERE, "hasy_cache.npz")

# curated HASYv2 symbols: latex code -> unicode glyph shown in the app.
# (+ - = × ÷ ( ) [ ] < > are left to synthsigns to avoid duplicate labels)
SYMBOLS = {
    # relations
    r"\pm": "±", r"\neq": "≠", r"\leq": "≤", r"\geq": "≥",
    r"\approx": "≈", r"\equiv": "≡", r"\sim": "∼", r"\simeq": "≃",
    r"\cong": "≅", r"\propto": "∝", r"\perp": "⊥",
    r"\lesssim": "≲", r"\gtrsim": "≳",
    # operators
    r"\ast": "∗", r"\sqrt{}": "√", r"\sum": "∑", r"\int": "∫",
    r"\oint": "∮", r"\prod": "∏", r"\partial": "∂", r"\nabla": "∇",
    r"\oplus": "⊕", r"\otimes": "⊗", r"\setminus": "∖", "/": "/",
    # arrows
    r"\rightarrow": "→", r"\Rightarrow": "⇒", r"\leftrightarrow": "↔",
    r"\Leftrightarrow": "⇔", r"\mapsto": "↦", r"\hookrightarrow": "↪",
    # set / logic
    r"\in": "∈", r"\notin": "∉", r"\subset": "⊂", r"\supset": "⊃",
    r"\subseteq": "⊆", r"\cup": "∪", r"\cap": "∩",
    r"\forall": "∀", r"\exists": "∃", r"\neg": "¬", r"\wedge": "∧",
    r"\vee": "∨", r"\emptyset": "∅", r"\vdash": "⊢", r"\therefore": "∴",
    # brackets
    r"\{": "{", r"\}": "}", r"\langle": "⟨", r"\rangle": "⟩",
    # misc
    r"\infty": "∞", r"\%": "%", r"\degree": "°", r"\#": "#", r"\&": "&",
    "|": "|", r"\aleph": "ℵ", r"\hbar": "ℏ", r"\lightning": "↯",
    r"\heartsuit": "♥", r"\checkmark": "✓", r"\pi": "π",
}

NAMES = list(SYMBOLS.values())


def _load_png(path):
    arr = np.asarray(Image.open(os.path.join(HASY_DIR, path)).convert("L").resize((28, 28)))
    return (255 - arr).astype("float32") / 255.0   # invert: black-on-white -> white-on-black


def _build_cache():
    by_code = {code: [] for code in SYMBOLS}
    with open(os.path.join(HASY_DIR, "hasy-data-labels.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["latex"] in by_code:
                by_code[row["latex"]].append(row["path"])

    imgs, labels = [], []
    for i, code in enumerate(SYMBOLS):
        for path in by_code[code]:
            imgs.append(_load_png(path))
        labels.append(np.full(len(by_code[code]), i, dtype="int64"))
    np.savez_compressed(CACHE, x=np.stack(imgs), y=np.concatenate(labels))


def load(usage="train", seed=0):
    if not os.path.exists(CACHE):
        _build_cache()
    d = np.load(CACHE)
    x, y = d["x"], d["y"]

    keep_x, keep_y = [], []
    for i in range(len(SYMBOLS)):
        sel = np.where(y == i)[0]
        perm = np.random.default_rng(seed + i).permutation(sel)
        cut = int(len(perm) * 0.9)
        pick = perm[:cut] if usage == "train" else perm[cut:]
        keep_x.append(x[pick])
        keep_y.append(y[pick])
    return np.concatenate(keep_x), np.concatenate(keep_y)
