"""Разрезание рисунка на символы и чтение строки из нескольких символов.

Сеть обучена на одиночных символах: весь холст она ужимает в один кадр 28x28,
и «65» для неё превращается в «W». Поэтому рисунок режется на символы по
мазкам: мазки, перекрывающиеся по горизонтали, - один символ («=», «i», «÷»
рисуются несколькими мазками друг над другом), стоящие рядом - разные.
Каждый символ идёт в сеть отдельно, через ту же normalize(), что и при обучении.

Модуль ничего не знает про окно: только мазки, картинки и вероятности.
"""
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

# Какая доля более узкой из двух частей должна перекрываться по горизонтали,
# чтобы они считались одним символом. Верхняя черта «5» и её крючок
# перекрываются почти целиком, а соседние цифры - нисколько или краешком.
OVERLAP = 0.3
# Если большинство символов - цифры, спорный символ читается цифрой, когда у
# лучшей цифры хотя бы столько: «6» и «b», «5» и «S», «0» и «O» сеть путает.
DIGIT_SWITCH = 0.10
DIGITS = frozenset("0123456789")
# Знаки, которые рукописью почти всегда означают цифру: одиночную палочку сеть
# называет «|» (99 %), круглый ноль толстой кистью - «°». Для подсчёта «тут
# число?» они идут как цифры.
DIGIT_SHAPES = {"|": "1", "°": "0"}
# Буквы, похожие на цифры. Меняются на цифру только в окружении цифр:
# «S5» - это «55», а «SOS» остаётся «SOS».
LOOKALIKES = {**DIGIT_SHAPES, "l": "1", "I": "1", "i": "1", "/": "1", "O": "0", "o": "0",
              "D": "0", "Q": "0", "Z": "2", "z": "2", "S": "5", "s": "5", "b": "6",
              "G": "6", "T": "7", "B": "8", "g": "9", "q": "9"}


@dataclass
class Stroke:
    width: int
    points: list = field(default_factory=list)

    @property
    def x0(self):
        return min(x for x, _ in self.points) - self.width / 2

    @property
    def x1(self):
        return max(x for x, _ in self.points) + self.width / 2


@dataclass
class Group:
    strokes: list

    @property
    def x0(self):
        return min(s.x0 for s in self.strokes)

    @property
    def x1(self):
        return max(s.x1 for s in self.strokes)


def group_strokes(strokes, overlap=OVERLAP):
    """Мазки -> символы слева направо. Каждый мазок попадает ровно в один."""
    groups = []
    for s in sorted((s for s in strokes if s.points), key=lambda s: s.x0):
        if groups:
            g = groups[-1]
            inter = min(g.x1, s.x1) - max(g.x0, s.x0)
            if inter >= overlap * min(s.x1 - s.x0, g.x1 - g.x0):
                g.strokes.append(s)
                continue
        groups.append(Group([s]))
    return groups


def paint_stroke(draw, stroke, fill=255):
    """Рисует мазок так же, как окно рисует его на холсте: линии и круглые концы."""
    r = stroke.width // 2
    pts = stroke.points
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        draw.line([(xa, ya), (xb, yb)], fill=fill, width=stroke.width)
        draw.ellipse([xb - r, yb - r, xb + r, yb + r], fill=fill)
    x, y = pts[0]
    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def render(strokes, size):
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    for s in strokes:
        if s.points:
            paint_stroke(draw, s)
    return img


def read_sequence(probs_list, labels):
    """Вероятности по каждому символу -> (выбранные классы, уверенность строки,
    уверенность каждого символа).

    Если символов несколько и хотя бы половина из них - цифры (или «|», «°»),
    строка читается как число: похожие буквы меняются на цифры, а спорный
    символ - на лучшую цифру, если у неё не меньше DIGIT_SWITCH.

    Уверенность символа - вероятность того, что сеть видела именно эту форму:
    для «|», прочитанной как «1», это вероятность «|» плюс «1». Уверенность
    строки - произведение: три символа по 90 % дают примерно 73 %, а не 90.
    """
    index = {name: i for i, name in enumerate(labels)}
    tops = [int(np.argmax(p)) for p in probs_list]
    chosen = list(tops)
    sure = [float(p[t]) for p, t in zip(probs_list, tops)]
    digit_idx = [i for i, name in enumerate(labels) if name in DIGITS]
    digitish = sum(labels[t] in DIGITS or labels[t] in DIGIT_SHAPES for t in tops)
    if digit_idx and len(tops) > 1 and digitish * 2 >= len(tops):
        for n, p in enumerate(probs_list):
            name = labels[tops[n]]
            if name in DIGITS:
                continue
            twin = LOOKALIKES.get(name)
            if twin in index:
                chosen[n] = index[twin]
                sure[n] = float(p[tops[n]] + p[index[twin]])
                continue
            best = max(digit_idx, key=lambda i: p[i])
            if p[best] >= DIGIT_SWITCH:
                chosen[n] = best
                sure[n] = float(p[best])
    return chosen, float(np.prod(sure)), sure


def join_labels(names):
    """«6», «5» -> «65»; «солнце», «дерево» -> «солнце дерево»."""
    return "".join(names) if all(len(n) == 1 for n in names) else " ".join(names)
