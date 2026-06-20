import os
import shutil
import urllib.request

import numpy as np

BASE = "https://storage.googleapis.com/quickdraw_dataset/full/numpy_bitmap/"
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quickdraw")

# Quick Draw category -> label shown in the app
CATEGORIES = {
    # shapes
    "circle": "круг",
    "square": "квадрат",
    "triangle": "треугольник",
    "star": "звезда",
    "line": "линия",
    "hexagon": "шестиугольник",
    "zigzag": "зигзаг",
    # objects
    "cat": "кошка",
    "dog": "собака",
    "house": "дом",
    "tree": "дерево",
    "car": "машина",
    "fish": "рыба",
    "flower": "цветок",
    "sun": "солнце",
    "cloud": "облако",
    "apple": "яблоко",
    "bird": "птица",
    "key": "ключ",
    "clock": "часы",
    "eye": "глаз",
    "umbrella": "зонт",
    "bicycle": "велосипед",
    "scissors": "ножницы",
    "airplane": "самолёт",
}

NAMES = list(CATEGORIES.values())


def _expected_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("content-length", 0))


def _fetch(url, path, want, tries=5):
    for attempt in range(1, tries + 1):
        try:
            tmp = path + ".part"
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, length=1 << 20)
            if want and os.path.getsize(tmp) != want:
                raise IOError(f"size mismatch {os.path.getsize(tmp)} != {want}")
            os.replace(tmp, path)
            return
        except Exception as e:
            print(f"  retry {attempt}/{tries} ({type(e).__name__})")
    raise RuntimeError(f"failed to download {url}")


def download_all():
    os.makedirs(DIR, exist_ok=True)
    for cat in CATEGORIES:
        path = os.path.join(DIR, f"{cat}.npy")
        url = BASE + cat.replace(" ", "%20") + ".npy"
        want = _expected_size(url)
        if os.path.exists(path) and os.path.getsize(path) == want:
            continue
        print("downloading", cat, "...")
        _fetch(url, path, want)
    print("quickdraw ready")


def load_shapes(per_class, usage="train", seed=0):
    imgs, labels = [], []
    for i, cat in enumerate(CATEGORIES):
        arr = np.load(os.path.join(DIR, f"{cat}.npy"))  # (N, 784) uint8
        perm = np.random.default_rng(seed).permutation(len(arr))
        cut = int(len(arr) * 0.9)
        pool = perm[:cut] if usage == "train" else perm[cut:]
        sel = pool[: min(per_class, len(pool))]
        imgs.append(arr[sel].reshape(-1, 28, 28))
        labels.append(np.full(len(sel), i, dtype="int64"))
    x = np.concatenate(imgs).astype("float32") / 255.0
    y = np.concatenate(labels)
    return x, y
