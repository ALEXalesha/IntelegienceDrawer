"""Окно «Нарисуй - угадаю» открывается там, где его закрыли (1.3.0). Размер у окна
постоянный, поэтому запоминается только место, а размер всегда задают виджеты."""
import json
import os
import sys

import pytest
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402
import tk_window_state  # noqa: E402


@pytest.fixture
def top(root):
    t = tk.Toplevel(root)
    yield t
    try:
        t.destroy()
    except tk.TclError:
        pass  # закрыли в самом тесте


def test_the_window_comes_back_where_it_was_closed(root, top, tmp_path):
    f = tmp_path / "window.json"
    first = app.DrawApp(top, f)
    top.update_idletasks()
    size = (top.winfo_reqwidth(), top.winfo_reqheight())
    area = tk_window_state.work_areas(top)[0]
    x, y = area["x"] + 40, area["y"] + 30
    top.geometry(f"+{x}+{y}")
    top.update()
    first.close()
    saved = json.loads(f.read_text(encoding="utf-8"))
    assert (saved["x"], saved["y"]) == (x, y)

    again = tk.Toplevel(root)
    try:
        app.DrawApp(again, f)
        again.update()
        g = tk_window_state.parse_geometry(again.wm_geometry())
        assert (g["x"], g["y"]) == (x, y)
        assert (g["width"], g["height"]) == size  # размер - от виджетов, не из файла
    finally:
        again.destroy()


def test_a_size_in_the_file_does_not_crop_the_widgets(root, top, tmp_path):
    f = tmp_path / "window.json"
    area = tk_window_state.work_areas(top)[0]
    f.write_text(json.dumps({"x": area["x"] + 10, "y": area["y"] + 10, "width": 50, "height": 50,
                             "maximized": True}), encoding="utf-8")
    app.DrawApp(top, f)
    top.update()
    g = tk_window_state.parse_geometry(top.wm_geometry())
    assert (g["width"], g["height"]) == (top.winfo_reqwidth(), top.winfo_reqheight())
    assert top.state() != "zoomed"


@pytest.mark.parametrize("text", ["", "{", "null", "[]", '{"x": "a"}'])
def test_a_broken_file_is_not_an_error(root, top, tmp_path, text):
    f = tmp_path / "window.json"
    f.write_text(text, encoding="utf-8")
    app.DrawApp(top, f)
    top.update()
    assert top.winfo_exists()


def test_the_window_file_lives_in_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert app.window_file() == os.path.join(str(tmp_path), "DrawGuess", "window.json")
