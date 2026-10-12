import math
import customtkinter as ctk

_WIDTH = 520
_MIN_HEIGHT = 190
_MAX_SCREEN_FRACTION = 0.8
_CHARS_PER_LINE = 62
_LINE_HEIGHT = 21
_CHROME_HEIGHT = 120  # title row + OK button + paddings


def _show_message(parent, title, message, heading_color=None):
    """
    Modal replacement for tkinter's messagebox. The message sits in a
    read-only scrollable textbox and the OK button lives in its own fixed
    row, so a long message (e.g. a list of warnings) scrolls instead of
    pushing the OK button off the bottom of the screen.
    """
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())

    # Size to the content, capped at a fraction of the screen height
    lines = sum(max(1, math.ceil(len(line) / _CHARS_PER_LINE)) for line in message.split("\n"))
    max_height = int(dialog.winfo_screenheight() * _MAX_SCREEN_FRACTION)
    height = min(max(_MIN_HEIGHT, lines * _LINE_HEIGHT + _CHROME_HEIGHT), max_height)

    # Center over the app window
    root = parent.winfo_toplevel()
    x = root.winfo_rootx() + (root.winfo_width() - _WIDTH) // 2
    y = root.winfo_rooty() + (root.winfo_height() - height) // 2
    dialog.geometry(f"{_WIDTH}x{height}+{max(x, 0)}+{max(y, 0)}")
    dialog.minsize(380, 160)

    dialog.grid_rowconfigure(0, weight=1)
    dialog.grid_columnconfigure(0, weight=1)

    textbox = ctk.CTkTextbox(dialog, wrap="word", font=ctk.CTkFont(size=13))
    textbox.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
    textbox.insert("1.0", message)
    textbox.configure(state="disabled")

    btn_ok = ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100)
    btn_ok.grid(row=1, column=0, pady=(0, 20))

    dialog.bind("<Return>", lambda e: dialog.destroy())
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    # Modal behavior - grab_set must run after the window exists. Block until
    # closed, like messagebox, so callers' try/finally blocks run afterwards.
    dialog.after(50, lambda: (dialog.grab_set(), dialog.focus_force(), btn_ok.focus_set()))
    parent.wait_window(dialog)


def show_info(parent, title, message):
    _show_message(parent, title, message)


def show_error(parent, title, message):
    _show_message(parent, title, message)
