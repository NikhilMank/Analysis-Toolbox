import customtkinter as ctk


def show_help_dialog(parent, title, content):
    """
    Opens a small modal window with plain-text usage instructions.
    Shared by every tool's "How to Use" button so the popup styling and
    behavior stay consistent across the app.

    Parameters
    ----------
    parent : the CTk widget opening the dialog (usually the tool's frame)
    title : window title, e.g. "How to Use: Difference Finder"
    content : the instructions text. Uses blank lines and dashes for
        structure rather than rich formatting, since the underlying
        textbox is plain text.
    """
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("480x460")
    dialog.minsize(400, 320)
    dialog.transient(parent)

    dialog.grid_rowconfigure(0, weight=1)
    dialog.grid_columnconfigure(0, weight=1)

    textbox = ctk.CTkTextbox(dialog, wrap="word", font=ctk.CTkFont(size=13))
    textbox.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
    textbox.insert("1.0", content)
    textbox.configure(state="disabled")  # read-only

    btn_close = ctk.CTkButton(dialog, text="Got it", command=dialog.destroy, width=100)
    btn_close.grid(row=1, column=0, pady=(0, 20))

    # Modal behavior - grab_set must run after the window exists
    dialog.grab_set()
    dialog.focus_force()