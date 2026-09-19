"""Один корень Tk на весь прогон.

Если создавать и разрушать много tk.Tk() в одном процессе, Tcl время от
времени падает при старте с «init.tcl ... tk wasn't installed properly».
Поэтому корень общий, а перед каждым тестом с него снимаются виджеты
прошлого окна.
"""
import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def root(tk_root):
    for child in tk_root.winfo_children():
        child.destroy()
    tk_root.resizable(True, True)
    for col in range(3):
        tk_root.grid_columnconfigure(col, weight=0, minsize=0)
    yield tk_root
    for child in tk_root.winfo_children():
        child.destroy()
