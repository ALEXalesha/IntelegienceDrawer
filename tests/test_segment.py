"""Разрезание на символы (segment.py) и чтение нескольких символов в окне."""
import math
import os
import random
import re
import sys
import tkinter as tk
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import segment  # noqa: E402
from segment import Stroke  # noqa: E402

W = 30


def line(x0, y0, x1, y1, n=8, w=W):
    return Stroke(w, [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)])


def ring(cx, cy, r, w=W, n=24, ry=None):
    ry = r if ry is None else ry
    return Stroke(w, [(cx + r * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n))
                      for i in range(n + 1)])


def dot(x, y, w=W):
    return Stroke(w, [(x, y)])


def xs(groups):
    return [(round(g.x0), round(g.x1)) for g in groups]


# ---- разрезание ----------------------------------------------------------------

def test_two_digits_side_by_side_are_two_symbols():
    six = ring(150, 300, 50)
    five_hook = ring(340, 320, 45)
    five_bar = line(310, 180, 440, 180)
    groups = segment.group_strokes([five_bar, six, five_hook])
    assert len(groups) == 2
    assert groups[0].strokes == [six], "символы не слева направо"
    assert set(map(id, groups[1].strokes)) == {id(five_hook), id(five_bar)}, "верх «5» оторвался"


@pytest.mark.parametrize("name, strokes", [
    ("=", [line(100, 200, 300, 200), line(110, 260, 290, 260)]),
    ("i", [line(200, 200, 200, 400), dot(200, 130)]),
    ("÷", [line(100, 250, 300, 250), dot(200, 180), dot(200, 320)]),
    ("+", [line(100, 250, 300, 250), line(200, 150, 200, 350)]),
    ("4", [line(150, 100, 100, 300), line(100, 300, 280, 300), line(230, 150, 230, 420)]),
    ("круг одним мазком", [ring(250, 250, 150)]),
])
def test_multi_stroke_symbols_stay_whole(name, strokes):
    assert len(segment.group_strokes(strokes)) == 1, name


def test_three_spaced_symbols_in_any_drawing_order():
    one, two, three = line(80, 150, 80, 350), ring(250, 250, 60), line(400, 150, 420, 350)
    for order in ([one, two, three], [three, one, two], [two, three, one]):
        groups = segment.group_strokes(order)
        assert [g.strokes for g in groups] == [[one], [two], [three]]


def test_empty_and_pointless_strokes():
    assert segment.group_strokes([]) == []
    assert segment.group_strokes([Stroke(W, [])]) == []


def test_random_drawings_keep_the_partition_invariants():
    """Любой набор мазков: каждый мазок ровно в одной группе, группы идут слева
    направо, и соседние группы перекрываются меньше порога."""
    rng = random.Random(3)
    for _ in range(500):
        strokes = []
        for _ in range(rng.randint(1, 9)):
            w = rng.randint(app.PEN_MIN, app.PEN_MAX)
            pts = [(rng.randint(0, 500), rng.randint(0, 500)) for _ in range(rng.randint(1, 6))]
            strokes.append(Stroke(w, pts))
        groups = segment.group_strokes(strokes)
        flat = [id(s) for g in groups for s in g.strokes]
        assert sorted(flat) == sorted(map(id, strokes)), "мазок потерялся или попал дважды"
        assert [g.x0 for g in groups] == sorted(g.x0 for g in groups)
        for a, b in zip(groups, groups[1:]):
            inter = min(a.x1, b.x1) - max(a.x0, b.x0)
            assert inter < segment.OVERLAP * min(a.x1 - a.x0, b.x1 - b.x0) + 1e-9 or \
                b.strokes[0].x0 >= a.strokes[-1].x0


def test_render_matches_the_window_drawing():
    """Картинка группы рисуется так же, как окно рисует на холсте: одиночный
    символ, отрендеренный заново, совпадает с тем, что нарисовал человек."""
    root = tk.Tk()
    root.withdraw()
    try:
        win = app.DrawApp(root)
        pts = [(100, 100), (180, 140), (220, 260), (160, 330)]
        win._press(SimpleNamespace(x=pts[0][0], y=pts[0][1]))
        for x, y in pts[1:]:
            win._move(SimpleNamespace(x=x, y=y))
        win.last = None
        again = segment.render(win.strokes, app.CANVAS)
        assert np.array_equal(np.asarray(again), np.asarray(win.image))
    finally:
        root.destroy()


# ---- чтение строки ---------------------------------------------------------------

LABELS = ["0", "1", "5", "6", "b", "S", "O", "A", "K", "|", "°", "кошка", "дом"]
ALIAS = {"zero": "0", "one": "1", "five": "5", "six": "6", "bar": "|", "deg": "°"}


def probs(**kw):
    p = np.full(len(LABELS), 1e-4)
    for name, v in kw.items():
        p[LABELS.index(ALIAS.get(name, name))] = v
    return p / p.sum()


def read(*ps):
    chosen, conf, sure = segment.read_sequence(list(ps), LABELS)
    return "".join(LABELS[c] for c in chosen), conf, sure


def test_lookalike_letter_next_to_a_digit_becomes_a_digit():
    """Случай со скриншота: «6» рядом с «5» сеть читает как «b»."""
    text, _, sure = read(probs(b=0.55, six=0.05), probs(five=0.9))
    assert text == "65"
    assert sure[0] == pytest.approx(probs(b=0.55, six=0.05)[4] + probs(b=0.55, six=0.05)[3]), \
        "уверенность «6» из «b» - это вероятность формы: b + 6"


def test_doubtful_symbol_takes_a_strong_enough_digit():
    text, _, sure = read(probs(A=0.6, six=0.3), probs(five=0.9))
    assert text == "65" and sure[0] == pytest.approx(probs(A=0.6, six=0.3)[3])


def test_a_weak_digit_does_not_win():
    text, _, _ = read(probs(A=0.9, six=0.05), probs(five=0.9))
    assert text == "A5", "цифра с 5 % перебила уверенную букву, не похожую на цифру"


def test_bars_and_degree_signs_read_as_numbers():
    """Одиночную палочку сеть называет «|», круглый ноль - «°»."""
    assert read(probs(bar=0.99), probs(deg=0.9))[0] == "10"
    assert read(probs(bar=0.99), probs(bar=0.97))[0] == "11"
    assert read(probs(bar=0.9), probs(zero=0.8), probs(O=0.7))[0] == "100"


def test_letters_in_majority_stay_letters():
    assert read(probs(S=0.8), probs(O=0.8), probs(S=0.8))[0] == "SOS"
    assert read(probs(S=0.6, five=0.3), probs(b=0.8), probs(K=0.7))[0] == "SbK"
    assert read(probs(A=0.8), probs(five=0.9), probs(K=0.8))[0] == "A5K"


def test_single_symbol_is_never_pulled():
    assert read(probs(b=0.55, six=0.4))[0] == "b"
    assert read(probs(bar=0.99))[0] == "|"


def test_confidence_is_the_product():
    a, b = probs(six=0.8), probs(five=0.5)
    _, conf, sure = read(a, b)
    assert conf == pytest.approx(a[3] * b[2]) == pytest.approx(sure[0] * sure[1])
    assert 0 <= conf <= 1


def test_random_reads_keep_their_invariants():
    """Любые вероятности: столько же символов, сколько групп; уверенность в
    [0, 1] и равна произведению; цифры не превращаются в не-цифры; без цифр и
    «|», «°» ничего не меняется."""
    rng = np.random.default_rng(5)
    for _ in range(2000):
        ps = [rng.dirichlet(np.full(len(LABELS), 0.3)) for _ in range(rng.integers(1, 6))]
        chosen, conf, sure = segment.read_sequence(ps, LABELS)
        tops = [int(np.argmax(p)) for p in ps]
        assert len(chosen) == len(ps) == len(sure)
        assert 0 <= conf <= 1 + 1e-9 and conf == pytest.approx(float(np.prod(sure)))
        assert all(0 <= s <= 1 + 1e-9 for s in sure)
        for t, c in zip(tops, chosen):
            if LABELS[t] in segment.DIGITS:
                assert c == t
        if not any(LABELS[t] in segment.DIGITS or LABELS[t] in segment.DIGIT_SHAPES for t in tops):
            assert chosen == tops


def test_join():
    assert segment.join_labels(["6", "5"]) == "65"
    assert segment.join_labels(["кошка", "дом"]) == "кошка дом"
    assert segment.join_labels(["2", "+", "2"]) == "2+2"


# ---- окно ------------------------------------------------------------------------

@pytest.fixture
def win():
    root = tk.Tk()
    root.withdraw()
    w = app.DrawApp(root)
    yield w
    root.destroy()


def draw(win, stroke):
    (x, y), rest = stroke.points[0], stroke.points[1:]
    win.pen.set(stroke.width)
    win._press(SimpleNamespace(x=round(x), y=round(y)))
    for x, y in rest:
        win._move(SimpleNamespace(x=round(x), y=round(y)))
    win._release(None)


def test_click_without_moving_leaves_a_dot(win):
    win._press(SimpleNamespace(x=250, y=250))
    win._release(None)
    assert np.asarray(win.image)[250, 250] == 255
    assert len(win.strokes) == 1 and win.canvas.find_all()


def test_clear_forgets_strokes(win):
    draw(win, line(100, 100, 100, 300))
    win.clear()
    assert win.strokes == []


def test_window_reads_several_symbols_with_a_fake_net(win):
    """Подставная сеть узнаёт символ по тому, где он стоит на холсте: левый - «6»,
    правый - «5». Окно обязано сказать «65» и показать каждый символ."""
    import torch

    n = len(win.labels)
    six, five = win.labels.index("6"), win.labels.index("5")
    calls = []

    def net(t):
        calls.append(t)
        p = torch.full((n,), 1e-4)
        p[six if len(calls) == 1 else five] = 0.9
        return torch.log(p / p.sum()).unsqueeze(0)

    win.net = net
    draw(win, ring(150, 250, 60))
    draw(win, line(330, 150, 450, 150))
    calls.clear()
    draw(win, ring(380, 290, 60))
    assert len(calls) == 2, "каждый символ должен идти в сеть отдельно"
    text = win.guess.cget("text")
    assert text.splitlines()[1].startswith("65"), text
    assert "По символам:" in text
    assert re.search(r"^6\s+\d+%", text, re.M) and re.search(r"^5\s+\d+%", text, re.M), text


def test_many_symbols_do_not_grow_the_window(win):
    root = win.root
    root.update_idletasks()
    before = (root.winfo_reqwidth(), root.winfo_reqheight())
    for k in range(12):                      # больше MAX_SYMBOLS
        x = 20 + k * 40
        draw(win, line(x, 150, x, 350, w=app.PEN_MIN))
    text = win.guess.cget("text")
    assert text.count("\n") <= 3 + app.MAX_SYMBOLS + 1
    assert len(text.splitlines()[1].split("   ")[0]) <= app.MAX_TEXT
    root.update_idletasks()
    assert (root.winfo_reqwidth(), root.winfo_reqheight()) == before


@pytest.mark.skipif(not os.path.exists(os.path.join(app.HERE, "model.pt")), reason="нет model.pt")
@pytest.mark.parametrize("expected, strokes", [
    ("10", [line(130, 130, 130, 370), ring(340, 250, 70, ry=120)]),
    ("10", [line(130, 130, 130, 370), ring(340, 250, 100)]),          # круглый ноль
    ("11", [line(150, 130, 150, 370), line(350, 130, 350, 370)]),
    ("70", [line(40, 130, 200, 130), line(200, 130, 100, 380), ring(360, 250, 70, ry=120)]),
])
def test_real_model_reads_numbers(win, expected, strokes):
    """Настоящая модель, числа из раздельных символов. Без разрезания вся
    картинка шла в сеть одним символом; без правила похожих знаков «1» была
    бы «|», а круглый «0» - «°»."""
    for s in strokes:
        draw(win, s)
    shown = win.guess.cget("text").splitlines()[1].split("   ")[0]
    assert shown == expected, win.guess.cget("text")
