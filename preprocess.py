import numpy as np
from PIL import Image

# Shared normalization so training data and the live drawing go through the
# exact same transform: crop to the ink, scale the longest side to 20 px,
# center inside a 28x28 frame (the classic MNIST framing).
TARGET = 20
FRAME = 28
THRESH = 0.1


def normalize(arr):
    """arr: HxW float in [0,1], white ink on black. -> 28x28 float in [0,1]."""
    ys, xs = np.where(arr > THRESH)
    if len(xs) == 0:
        return np.zeros((FRAME, FRAME), dtype="float32")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = Image.fromarray((arr[y0:y1 + 1, x0:x1 + 1] * 255).astype("uint8"))

    w, h = crop.size
    scale = TARGET / max(w, h)
    small = crop.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)

    frame = Image.new("L", (FRAME, FRAME), 0)
    nw, nh = small.size
    frame.paste(small, ((FRAME - nw) // 2, (FRAME - nh) // 2))
    return np.asarray(frame, dtype="float32") / 255.0


def normalize_batch(stack):
    return np.stack([normalize(im) for im in stack])
