import customtkinter as ctk

from ui.help_content import HELP_CONTENT, LANGUAGES, UI_STRINGS
from utils.config import get_setting, update_setting


def show_help_dialog(parent, tool_key):
    """
    Opens a small modal window with plain-text usage instructions, with a
    language dropdown to switch between translations. Shared by every
    tool's "How to Use" button so the popup styling and behavior stay
    consistent across the app.

    Parameters
    ----------
    parent : the CTk widget opening the dialog (usually the tool's frame)
    tool_key : key into HELP_CONTENT identifying which tool's translations
        to show (e.g. "difference", "packet_generator")
    """
    translations = HELP_CONTENT[tool_key]

    lang = get_setting("language")
    if lang not in translations:
        lang = "en"

    name_to_code = {name: code for code, name in LANGUAGES.items() if code in translations}

    dialog = ctk.CTkToplevel(parent)
    dialog.geometry("480x460")
    dialog.minsize(400, 320)
    dialog.transient(parent)

    dialog.grid_rowconfigure(1, weight=1)
    dialog.grid_columnconfigure(0, weight=1)

    def render(code):
        entry = translations[code]
        dialog.title(entry["title"])
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("1.0", entry["content"])
        textbox.configure(state="disabled")
        btn_close.configure(text=UI_STRINGS.get(code, UI_STRINGS["en"])["got_it"])

    def on_language_change(name):
        code = name_to_code[name]
        update_setting("language", code)
        render(code)

    language_var = ctk.StringVar(value=LANGUAGES[lang])
    option_language = ctk.CTkOptionMenu(
        dialog,
        values=list(name_to_code),
        variable=language_var,
        command=on_language_change,
        width=140
    )
    option_language.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")

    textbox = ctk.CTkTextbox(dialog, wrap="word", font=ctk.CTkFont(size=13))
    textbox.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nsew")

    btn_close = ctk.CTkButton(dialog, text="Got it", command=dialog.destroy, width=100)
    btn_close.grid(row=2, column=0, pady=(0, 20))

    render(lang)

    # Modal behavior - grab_set must run after the window exists
    dialog.grab_set()
    dialog.focus_force()
