"""Снимок окна для README: собирается программой, а не руками.

    python tools\\make_screenshot.py

Скрипт открывает настоящее окно приложения, рисует в нём несколько символов (вызывая те
же обработчики мыши, что и живая рука), ждёт ответа сети и снимает окно.

Окно на tkinter, и у его виджетов нет grab(), как у Qt. Поэтому снимок делается через
PrintWindow: Windows сама перерисовывает окно в картинку. Это важнее, чем кажется:
снимок области экрана по прямоугольнику окна захватил бы всё, что оказалось сверху, -
а только что открытое окно легко оказывается позади чужих.
"""

import ctypes
import math
import os
import sys
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PIL import Image  # noqa: E402

from app import DrawApp  # noqa: E402

PW_RENDERFULLCONTENT = 2
DWMWA_EXTENDED_FRAME_BOUNDS = 9


class FakeEvent:
    """Обработчикам мыши нужны только координаты."""

    def __init__(self, x, y):
        self.x, self.y = x, y


def draw(app, points):
    app._press(FakeEvent(*points[0]))
    for p in points[1:]:
        app._move(FakeEvent(*p))
    app._release(FakeEvent(*points[-1]))


def capture(hwnd, path):
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top

    src = user32.GetWindowDC(hwnd)
    dc = gdi32.CreateCompatibleDC(src)
    bmp = gdi32.CreateCompatibleBitmap(src, w, h)
    gdi32.SelectObject(dc, bmp)
    if not user32.PrintWindow(hwnd, dc, PW_RENDERFULLCONTENT):
        raise RuntimeError("PrintWindow не смог перерисовать окно")

    buf = ctypes.create_string_buffer(w * h * 4)
    header = ctypes.c_buffer(40 + 8)
    ctypes.memset(header, 0, len(header))
    ctypes.memmove(header, (ctypes.c_int32 * 11)(40, w, -h, 1 | (32 << 16), 0, w * h * 4, 0, 0, 0, 0, 0), 44)
    gdi32.GetDIBits(dc, bmp, 0, h, buf, header, 0)

    image = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(dc)
    user32.ReleaseDC(hwnd, src)

    # GetWindowRect в Windows 10/11 включает невидимые рамки для растягивания - около
    # 7 px слева, справа и снизу. PrintWindow рисует их чёрными, и в первом кадре для
    # README справа и снизу стояли чёрные полосы. Видимую границу окна знает DWM.
    frame = wintypes.RECT()
    if not ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(frame), ctypes.sizeof(frame)):
        image = image.crop((frame.left - rect.left, frame.top - rect.top,
                            frame.right - rect.left, frame.bottom - rect.top))
    image.save(path)
    return image.size


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = DrawApp(root)
    root.update()

    # «10» двумя цифрами: сеть обучена на одиночных символах, строку собирает segment.py.
    draw(app, [(150, 130), (170, 110), (170, 390)])                                # 1
    ring = [(360 + 80 * math.sin(t / 28 * 2 * math.pi), 250 - 130 * math.cos(t / 28 * 2 * math.pi))
            for t in range(29)]                                                    # 0
    draw(app, ring)
    root.update()

    hwnd = int(root.wm_frame(), 16)
    shot = OUT / "window.png"
    w, h = capture(hwnd, str(shot))
    print(f"  {shot.name} {w}x{h} ({shot.stat().st_size // 1024} КБ)")
    root.destroy()


if __name__ == "__main__":
    main()
