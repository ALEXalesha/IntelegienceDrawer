import gzip
import os
import struct
import zipfile

import numpy as np

# EMNIST archive downloaded from NIST. Standard IDX files inside, same as MNIST.
ZIP_PATH = os.path.expanduser("~/.cache/emnist/emnist.zip")

# EMNIST stores glyphs rotated/mirrored vs. how a human writes them.
# Swapping the two spatial axes turns them upright so they match canvas drawings.
TRANSPOSE = True


def _read_idx(raw_gz):
    raw = gzip.decompress(raw_gz)
    magic = struct.unpack(">I", raw[:4])[0]
    ndim = magic & 0xFF
    dims = struct.unpack(">" + "I" * ndim, raw[4 : 4 + 4 * ndim])
    body = np.frombuffer(raw[4 + 4 * ndim :], dtype=np.uint8)
    return body.reshape(dims)


def load_split(split, limit=None, seed=0):
    usage = "train" if split == "train" else "test"
    with zipfile.ZipFile(ZIP_PATH) as z:
        imgs = _read_idx(z.read(f"gzip/emnist-byclass-{usage}-images-idx3-ubyte.gz"))
        labels = _read_idx(z.read(f"gzip/emnist-byclass-{usage}-labels-idx1-ubyte.gz"))

    if TRANSPOSE:
        imgs = np.transpose(imgs, (0, 2, 1))

    if limit is not None and limit < len(imgs):
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(imgs), size=limit, replace=False)
        imgs, labels = imgs[idx], labels[idx]

    return imgs.astype("float32") / 255.0, labels.astype("int64")
