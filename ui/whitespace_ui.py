import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from utils.config import get_setting, update_setting
from tools.whitespace import run_whitespace_cleanup
from ui.help_dialog import show_help_dialog

class WhitespaceFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")

        self.input_file_path = ""
        self.has_header_var = ctk.BooleanVar(value=False)

        self.grid_columnconfigure(0, weight=1)

        # 1. Title (with "How to Use" button alongside it)
        self.title_row = ctk.CTkFrame(self, fg_color="transparent")
        self.title_row.grid(row=0, column=0, padx=40, pady=(40, 20), sticky="ew")
        self.title_row.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.title_row,
            text="Whitespace Cleaner",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.btn_help = ctk.CTkButton(
            self.title_row, text="❓ How to Use", width=120, height=28,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), hover_color=("gray85", "gray20"),
            font=ctk.CTkFont(size=12),
            command=self.show_help
        )
        self.btn_help.grid(row=0, column=1, sticky="e")

        # Description
        self.desc_label = ctk.CTkLabel(
            self,
            text="Strip leading and trailing whitespace from every cell. Saves a cleaned copy next to the original.",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.desc_label.grid(row=1, column=0, padx=40, pady=(0, 30), sticky="w")

        # 2. File Selection Group
        self.file_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_frame.grid(row=2, column=0, padx=40, pady=10, sticky="ew")
        self.file_frame.grid_columnconfigure(1, weight=1)

        self.btn_browse = ctk.CTkButton(
            self.file_frame, text="Select Data File", width=120, command=self.browse_file
        )
        self.btn_browse.grid(row=0, column=0, padx=(0, 10), pady=5)

        self.lbl_file = ctk.CTkLabel(
            self.file_frame, text="No file selected...", anchor="w", text_color="gray"
        )
        self.lbl_file.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 3. Header Option - user decides per run whether the file has a header row
        self.chk_has_header = ctk.CTkCheckBox(
            self,
            text="File includes a header row (first row is column titles, not data)",
            variable=self.has_header_var,
            onvalue=True,
            offvalue=False
        )
        self.chk_has_header.grid(row=3, column=0, padx=40, pady=(10, 0), sticky="w")

        # 4. Action Button (Run)
        self.btn_run = ctk.CTkButton(
            self,
            text="Trim Whitespace",
            fg_color="#2c8558",
            hover_color="#216341",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self.execute_tool
        )
        self.btn_run.grid(row=4, column=0, padx=40, pady=40, sticky="w")

    def get_initial_dir(self):
        last_dir = get_setting("last_opened_folder")
        if os.path.exists(last_dir):
            return last_dir
        return os.path.expanduser("~")

    def show_help(self):
        show_help_dialog(self, "whitespace")

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.get_initial_dir(),
            title="Select File to Clean",
            filetypes=[("Data files", "*.xlsx *.csv"), ("All Files", "*.*")]
        )
        if file_path:
            self.input_file_path = file_path
            self.lbl_file.configure(text=os.path.basename(file_path), text_color=("black", "white"))
            update_setting("last_opened_folder", os.path.dirname(file_path))

    def execute_tool(self):
        """Validates inputs, triggers the backend script, and displays intelligent notifications."""
        if not self.input_file_path:
            messagebox.showerror("Error", "Please select a file to process before running.")
            return

        self.btn_run.configure(state="disabled", text="Processing...")
        self.update()

        try:
            saved_path, cells_trimmed = run_whitespace_cleanup(
                self.input_file_path,
                has_header=self.has_header_var.get()
            )

            if not saved_path:
                messagebox.showinfo(
                    "Already Clean!",
                    "No leading or trailing whitespace was found.\nNo new file was created."
                )
            else:
                entry_word = "entry" if cells_trimmed == 1 else "entries"
                messagebox.showinfo(
                    "Success!",
                    f"Trimmed {cells_trimmed:,} {entry_word}.\n\n"
                    f"Saved as: {os.path.basename(saved_path)}\n\n"
                    f"Saved in directory:\n{os.path.dirname(self.input_file_path)}"
                )

        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred:\n\n{str(e)}")
        finally:
            self.btn_run.configure(state="normal", text="Trim Whitespace")
            