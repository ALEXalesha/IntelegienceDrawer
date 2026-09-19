"""Окно «Нарисуй - угадаю»: фиксированный размер, рисование, очистка, вывод догадок.

Окна настоящие (tkinter), но скрытые: withdraw() до первой отрисовки.
"""
import json
import os
import re
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def win(root):
    return app.DrawApp(root)


def ev(x, y):
    return SimpleNamespace(x=x, y=y)


def stroke(win, points):
    win._press(ev(*points[0]))
    for p in points[1:]:
        win._move(ev(*p))
    win._release(None)


def size(root):
    root.update_idletasks()
    return root.winfo_reqwidth(), root.winfo_reqheight()


def test_window_cannot_be_resized(win, root):
    assert tuple(bool(v) for v in root.resizable()) == (False, False)


def test_window_size_never_follows_the_guess_text(win, root):
    """Ресайза нет, но Tk сам подгоняет окно под содержимое. Самая длинная
    выдача (8 строк, два заголовка) не должна менять размер окна."""
    before = size(root)
    labels = json.load(open(os.path.join(HERE, "labels.json"), encoding="utf-8"))
    longest = max(labels, key=len)
    lines = [f"{longest}   {99:4.0f}%"] * 4
    win.guess.config(text="Думаю это:\n" + "\n".join(lines) + "\n\nНе уверен:\n" + "\n".join(lines))
    assert size(root) == before
    win.guess.config(text="")
    assert size(root) == before
    stroke(win, [(100, 100), (400, 400), (100, 400)])
    assert size(root) == before


def test_empty_canvas_gives_no_tensor():
    img = app.Image.new("L", (app.CANVAS, app.CANVAS), 0)
    assert app.canvas_to_tensor(img) is None


def test_stroke_lands_in_the_image_and_on_the_canvas(win):
    stroke(win, [(50, 60), (200, 60)])
    arr = np.asarray(win.image)
    assert arr[60, 50] == 255 and arr[60, 200] == 255 and arr[60, 125] == 255
    assert arr[400, 400] == 0, "краска там, где не рисовали"
    assert win.canvas.find_all(), "на холсте ничего не нарисовано"
    assert win.last is None, "после отпускания кисть не поднялась"


def test_pen_width_controls_the_stroke(win):
    win.pen.set(app.PEN_MIN)
    stroke(win, [(100, 100), (300, 100)])
    thin = int((np.asarray(win.image) > 0).sum())
    win.clear()
    win.pen.set(app.PEN_MAX)
    stroke(win, [(100, 100), (300, 100)])
    thick = int((np.asarray(win.image) > 0).sum())
    assert thick > thin * 3


def test_clear_resets_everything(win):
    stroke(win, [(10, 10), (490, 490)])
    win.clear()
    assert not np.asarray(win.image).any()
    assert win.canvas.find_all() == ()
    assert win.guess.cget("text") == "Нарисуй что-нибудь"


def test_tensor_shape_and_shift_invariance(win):
    stroke(win, [(100, 100), (160, 100), (160, 160)])
    a = app.canvas_to_tensor(win.image)
    win.clear()
    stroke(win, [(300, 280), (360, 280), (360, 340)])
    b = app.canvas_to_tensor(win.image)
    assert tuple(a.shape) == (1, 1, 28, 28)
    assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0
    assert np.allclose(a.numpy(), b.numpy(), atol=1e-4), "тот же рисунок в другом месте холста - другой вход сети"


@pytest.mark.skipif(not os.path.exists(os.path.join(HERE, "model.pt")), reason="нет model.pt")
def test_guess_text_follows_its_rules(win):
    stroke(win, [(150, 150), (350, 150), (350, 350), (150, 350), (150, 150)])
    text = win.guess.cget("text")
    assert text != "Нарисуй что-нибудь"
    percents = [int(m) for m in re.findall(r"(\d+)%", text)]
    assert 1 <= len(percents) <= 8
    assert percents == sorted(percents, reverse=True), "варианты не по убыванию"
    if "Думаю это:" in text:
        sure = text.split("Не уверен:")[0]
        assert all(int(p) >= 30 for p in re.findall(r"(\d+)%", sure))
    if "Не уверен:" in text:
        unsure = text.split("Не уверен:")[1]
        assert all(int(p) < 30 for p in re.findall(r"(\d+)%", unsure))


def test_guess_blocks_split_at_thirty_percent(win):
    """Подставная сеть с известными вероятностями: граница 30 % между «Думаю
    это» и «Не уверен», отсечка ниже 2 % и не больше 8 строк."""
    import torch

    n = len(win.labels)
    probs = torch.full((n,), 1e-6)
    probs[:10] = torch.tensor([0.40, 0.31, 0.12, 0.05, 0.04, 0.03, 0.025, 0.021, 0.02, 0.005])
    win.net = lambda _t: torch.log(probs / probs.sum()).unsqueeze(0)
    stroke(win, [(100, 100), (200, 200)])
    text = win.guess.cget("text")
    sure, unsure = text.split("Не уверен:")
    assert [win.labels[0] in sure, win.labels[1] in sure] == [True, True]
    assert win.labels[2] not in sure and win.labels[2] in unsure
    assert len(re.findall(r"%", text)) == 8, "больше восьми строк или отсечка не та"


def test_missing_model_is_explained(win):
    win.net = None
    stroke(win, [(100, 100), (200, 200)])
    assert "model.pt" in win.guess.cget("text")
