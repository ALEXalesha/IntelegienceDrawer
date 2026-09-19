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
# Буквы, у которых строчная и заглавная - одна и та же форма. Нормализация
# растягивает каждый символ до одного размера, и сеть их не различает. В строке
# размер виден: такую букву сравниваем по высоте с символами, чей рост известен
# (цифры, заглавные, строчные с верхним выносом), и выбираем регистр.
SAME_SHAPE = frozenset("cosuvwxz")
TALL = frozenset("0123456789ABDEFGHIJKLMNPQRTYbdfhklt")
SMALL_RATIO = 0.75   # ниже 3/4 высоты высоких символов - строчная
# Внутри надписи «кошка» или «рыба» почти наверняка ошибка: если хотя бы
# половина символов - знаки, картинка меняется на лучший знак, если у него
# хотя бы столько.
CHAR_SWITCH = 0.10


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

    @property
    def y0(self):
        return min(y for _, y in self.points) - self.width / 2

    @property
    def y1(self):
        return max(y for _, y in self.points) + self.width / 2


@dataclass
class Group:
    strokes: list

    @property
    def x0(self):
        return min(s.x0 for s in self.strokes)

    @property
    def x1(self):
        return max(s.x1 for s in self.strokes)

    @property
    def height(self):
        return max(s.y1 for s in self.strokes) - min(s.y0 for s in self.strokes)


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


def read_sequence(probs_list, labels, heights=None):
    """Вероятности по символам -> (выбранные классы, уверенность строки, уверенность символов).

    Правила по очереди:
    1. Число: если хотя бы половина символов - цифры (или «|», «°»), похожие
       знаки меняются на цифры, спорный символ - на лучшую цифру, если у неё
       не меньше DIGIT_SWITCH.
    2. Надпись: если хотя бы половина символов - знаки (не картинки вроде
       «кошка»), картинка меняется на лучший знак, если у него не меньше
       CHAR_SWITCH.
    3. Слово: если хотя бы половина - латинские буквы, спорный символ меняется
       на лучшую букву, если у неё не меньше CHAR_SWITCH.
    4. Регистр (если известны высоты): c, o, s, u, v, w, x, z ниже 3/4 роста
       высоких символов строки - строчные, иначе заглавные.
    Уверенность строки - произведение уверенностей символов.
    """
    chosen, sure = _read_numbers(probs_list, labels)
    if len(chosen) > 1:
        _prefer_characters(probs_list, labels, chosen, sure)
        _read_words(probs_list, labels, chosen, sure)
        if heights is not None:
            _fix_case(probs_list, labels, heights, chosen, sure)
    return chosen, float(np.prod(sure)), sure


def is_letter(name):
    return len(name) == 1 and name.isascii() and name.isalpha()


def _read_words(probs_list, labels, chosen, sure):
    """Слово: если хотя бы половина символов - латинские буквы (и строка не
    число), спорный символ меняется на лучшую букву, если у неё не меньше
    CHAR_SWITCH. Рукописную «a» сеть часто зовёт «2» или «d», а «a» ставит
    второй с 20 %: рядом с буквами это «a»."""
    letters = [i for i, name in enumerate(labels) if is_letter(name)]
    names = [labels[c] for c in chosen]
    numeric = sum(n in DIGITS for n in names) * 2 >= len(names)
    if not letters or numeric or sum(map(is_letter, names)) * 2 < len(names):
        return
    for n, p in enumerate(probs_list):
        if is_letter(labels[chosen[n]]):
            continue
        best = max(letters, key=lambda i: p[i])
        if p[best] >= CHAR_SWITCH:
            chosen[n] = best
            sure[n] = float(p[best])


def _prefer_characters(probs_list, labels, chosen, sure):
    chars = [i for i, name in enumerate(labels) if len(name) == 1]
    if not chars or sum(len(labels[c]) == 1 for c in chosen) * 2 < len(chosen):
        return
    for n, p in enumerate(probs_list):
        if len(labels[chosen[n]]) == 1:
            continue
        best = max(chars, key=lambda i: p[i])
        if p[best] >= CHAR_SWITCH:
            chosen[n] = best
            sure[n] = float(p[best])


def _fix_case(probs_list, labels, heights, chosen, sure):
    index = {name: i for i, name in enumerate(labels)}
    tall = [h for c, h in zip(chosen, heights) if labels[c] in TALL]
    if not tall:
        return
    ref = max(tall)
    for n, p in enumerate(probs_list):
        name = labels[chosen[n]]
        if name.lower() not in SAME_SHAPE:
            continue
        want = name.lower() if heights[n] < SMALL_RATIO * ref else name.upper()
        if want != name and want in index:
            twin = index[want]
            sure[n] = float(p[chosen[n]] + p[twin])
            chosen[n] = twin


def _read_numbers(probs_list, labels):
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
    return chosen, sure


def join_labels(names):
    """«6», «5» -> «65»; «солнце», «дерево» -> «солнце дерево»."""
    return "".join(names) if all(len(n) == 1 for n in names) else " ".join(names)


def alternative(p, chosen, labels):
    """Лучший другой вариант символа, кроме выбранного и того, из которого он
    получился («|» у единицы, «C» у «c» показывать незачем)."""
    name = labels[chosen]
    skip = {chosen} | {i for i, other in enumerate(labels)
                       if LOOKALIKES.get(other) == name
                       or (other != name and other.lower() == name.lower() and name.lower() in SAME_SHAPE)}
    return max((i for i in range(len(p)) if i not in skip), key=lambda i: p[i])
