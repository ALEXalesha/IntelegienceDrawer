import json
import os
import sys
import tkinter as tk

import numpy as np
import torch
from PIL import Image, ImageDraw

import segment
from model import SketchNet
from preprocess import normalize

CANVAS = 500          # on-screen drawing area in pixels
PEN_DEFAULT = 30      # starting stroke width
PEN_MIN, PEN_MAX = 8, 60
# Сколько символов строки показывать построчно и сколько знаков в самой строке:
# панель справа фиксированной ширины (22 знака) и высоты, окно не растягивается.
MAX_SYMBOLS = 8
MAX_TEXT = 14
# When frozen by PyInstaller, bundled data lives under sys._MEIPASS.
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def canvas_to_tensor(img):
    """Drawing (white strokes on black) -> (1, 1, 28, 28) tensor.
    Uses the same normalize() as training so the two never drift apart."""
    arr = np.asarray(img, dtype="float32") / 255.0
    if not (arr > 0).any():
        return None
    px = normalize(arr)
    return torch.from_numpy(px).unsqueeze(0).unsqueeze(0)


class DrawApp:
    def __init__(self, root):
        self.root = root
        root.title("Нарисуй - угадаю")
        ico = os.path.join(HERE, "drawguess.ico")
        if os.path.exists(ico):
            root.iconbitmap(ico)

        self.net, self.labels = self._load_model()

        self.canvas = tk.Canvas(root, width=CANVAS, height=CANVAS, bg="black",
                                cursor="crosshair")
        self.canvas.grid(row=0, column=0, rowspan=5, padx=10, pady=10)

        self.image = Image.new("L", (CANVAS, CANVAS), 0)
        self.draw = ImageDraw.Draw(self.image)
        self.last = None
        # Мазки по отдельности: по ним рисунок режется на символы (segment.py).
        self.strokes = []

        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._release)

        self.guess = tk.Label(root, text="Нарисуй что-нибудь",
                              font=("Segoe UI Symbol", 14), justify="left", anchor="w", width=22)
        self.guess.grid(row=0, column=1, sticky="nw", padx=6, pady=10)

        tk.Button(root, text="Очистить", command=self.clear).grid(
            row=1, column=1, sticky="ew", padx=6)

        self.pen = tk.IntVar(value=PEN_DEFAULT)
        tk.Label(root, text="Толщина кисти").grid(row=2, column=1, sticky="sw", padx=6)
        tk.Scale(root, from_=PEN_MIN, to=PEN_MAX, orient="horizontal",
                 variable=self.pen).grid(row=3, column=1, sticky="ew", padx=6)

        # Холст фиксированный (500x500, под него обучена нормализация), и
        # растягивать окну нечего: при ресайзе появлялись только пустые поля,
        # а Tk при этом заметно тормозил. Размер окна фиксирован, кнопка
        # «Развернуть» выключена.
        root.resizable(False, False)

    def _load_model(self):
        path = os.path.join(HERE, "model.pt")
        if not os.path.exists(path):
            return None, None
        labels = json.load(open(os.path.join(HERE, "labels.json"), encoding="utf-8"))
        net = SketchNet(num_classes=len(labels))
        net.load_state_dict(torch.load(path, map_location="cpu"))
        net.eval()
        return net, labels

    def _press(self, e):
        self.last = (e.x, e.y)
        w = self.pen.get()
        self.strokes.append(segment.Stroke(w, [(e.x, e.y)]))
        # Точка от простого щелчка: без неё у «i», «j», «÷» и «:» пропадали
        # точки - рисовалось только движение мыши.
        r = w // 2
        self.canvas.create_oval(e.x - r, e.y - r, e.x + r, e.y + r, fill="white", outline="white")
        self.draw.ellipse([e.x - r, e.y - r, e.x + r, e.y + r], fill=255)

    def _move(self, e):
        if self.last is None:
            self._press(e)
        x, y = e.x, e.y
        w = self.strokes[-1].width
        self.canvas.create_line(*self.last, x, y, fill="white",
                                width=w, capstyle=tk.ROUND, smooth=True)
        self.draw.line([self.last, (x, y)], fill=255, width=w)
        r = w // 2
        self.draw.ellipse([x - r, y - r, x + r, y + r], fill=255)
        self.strokes[-1].points.append((x, y))
        self.last = (x, y)

    def _release(self, _):
        self.last = None
        self.predict()

    def clear(self):
        self.canvas.delete("all")
        self.draw.rectangle([0, 0, CANVAS, CANVAS], fill=0)
        self.strokes = []
        self.guess.config(text="Нарисуй что-нибудь")

    def _probs(self, img):
        t = canvas_to_tensor(img)
        if t is None:
            return None
        with torch.no_grad():
            return torch.softmax(self.net(t), 1)[0].numpy()

    def predict(self):
        if self.net is None:
            self.guess.config(text="Нет model.pt.\nСначала: python train.py")
            return
        groups = segment.group_strokes(self.strokes)
        if len(groups) > 1:
            self._predict_sequence(groups)
            return
        probs = self._probs(self.image)
        if probs is None:
            return
        order = np.argsort(-probs)

        sure, unsure = [], []
        for i in order:
            pr = float(probs[i])
            if pr < 0.02 or len(sure) + len(unsure) >= 8:
                break
            line = f"{self.labels[i]}   {pr * 100:4.0f}%"
            (sure if pr >= 0.30 else unsure).append(line)

        blocks = []
        if sure:
            blocks.append("Думаю это:\n" + "\n".join(sure))
        if unsure:
            blocks.append("Не уверен:\n" + "\n".join(unsure))
        self.guess.config(text="\n\n".join(blocks) if blocks else "Не пойму что это")

    def _predict_sequence(self, groups):
        """Несколько символов рядом: каждый распознаётся отдельно, читаем слева направо."""
        probs_list = [self._probs(segment.render(g.strokes, CANVAS)) for g in groups]
        probs_list = [p for p in probs_list if p is not None]
        if not probs_list:
            return
        chosen, confidence, sure = segment.read_sequence(probs_list, self.labels)
        text = segment.join_labels([self.labels[c] for c in chosen])
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT - 1] + "…"

        lines = []
        for p, c, s in list(zip(probs_list, chosen, sure))[:MAX_SYMBOLS]:
            line = f"{self.labels[c]}  {s * 100:3.0f}%"
            # Лучший другой вариант, кроме выбранного и того, из которого он
            # получился («|» у единицы показывать незачем).
            skip = {c} | {i for i in range(len(p)) if segment.LOOKALIKES.get(self.labels[i]) == self.labels[c]}
            alt = max((i for i in range(len(p)) if i not in skip), key=lambda i: p[i])
            if p[alt] >= 0.02:
                line += f"   {self.labels[alt]} {p[alt] * 100:.0f}%"
            lines.append(line)
        if len(probs_list) > MAX_SYMBOLS:
            lines.append("…")
        head = "Думаю это:" if confidence >= 0.30 else "Не уверен:"
        self.guess.config(text=f"{head}\n{text}   {confidence * 100:.0f}%\n\nПо символам:\n" + "\n".join(lines))


if __name__ == "__main__":
    root = tk.Tk()
    DrawApp(root)
    root.mainloop()
