import json
import os
import time

import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader

from model import SketchNet, CLASS_CHARS
from data import load_split
from preprocess import normalize_batch
import quickdraw
import synthsigns
import mathsigns

EPOCHS = 10
BATCH = 512
SHAPE_PER_CLASS = 10_000
SYNTH_PER_CLASS = 4_000

LABELS = CLASS_CHARS + quickdraw.NAMES + synthsigns.NAMES + mathsigns.NAMES

OFF_SHAPE = len(CLASS_CHARS)
OFF_SYNTH = OFF_SHAPE + len(quickdraw.NAMES)
OFF_HASY = OFF_SYNTH + len(synthsigns.NAMES)


def assemble(usage):
    cache = f"assembled_{usage}.npz"
    if os.path.exists(cache):
        d = np.load(cache)
        return d["x"], d["y"]

    train = usage == "train"
    ex, ey = load_split("train" if train else "test")
    qx, qy = quickdraw.load_shapes(SHAPE_PER_CLASS if train else 2_000, usage=usage)
    sx, sy = synthsigns.make(SYNTH_PER_CLASS if train else 600, seed=0 if train else 99)
    hx, hy = mathsigns.load(usage=usage)

    x = np.concatenate([ex, qx, sx, hx])
    y = np.concatenate([ey, qy + OFF_SHAPE, sy + OFF_SYNTH, hy + OFF_HASY])

    print(f"  normalizing {len(x)} {usage} images ...")
    x = normalize_batch(x)
    np.savez_compressed(cache, x=x, y=y)
    return x, y


def to_loader(usage, batch, shuffle):
    x, y = assemble(usage)
    ds = TensorDataset(torch.from_numpy(x).unsqueeze(1), torch.from_numpy(y))
    return DataLoader(ds, batch_size=batch, shuffle=shuffle)


def evaluate(net, dl, device):
    net.eval()
    correct = total = 0
    with torch.no_grad():
        for xb, yb in dl:
            pred = net(xb.to(device)).argmax(1).cpu()
            correct += (pred == yb).sum().item()
            total += yb.numel()
    return correct / total


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", device, "| classes:", len(LABELS))

    quickdraw.download_all()
    train_dl = to_loader("train", BATCH, shuffle=True)
    test_dl = to_loader("test", 1024, shuffle=False)

    net = SketchNet(num_classes=len(LABELS)).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    sched = torch.optim.lr_scheduler.StepLR(opt, step_size=3, gamma=0.5)
    loss_fn = torch.nn.CrossEntropyLoss()

    for epoch in range(EPOCHS):
        net.train()
        t0 = time.time()
        for xb, yb in train_dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss_fn(net(xb), yb).backward()
            opt.step()
        sched.step()
        acc = evaluate(net, test_dl, device)
        print(f"epoch {epoch + 1}/{EPOCHS}  test_acc={acc:.3f}  ({time.time() - t0:.0f}s)")

    torch.save(net.state_dict(), "model.pt")
    with open("labels.json", "w", encoding="utf-8") as f:
        json.dump(LABELS, f, ensure_ascii=False)
    print(f"saved model.pt + labels.json ({len(LABELS)} classes)")


if __name__ == "__main__":
    main()
