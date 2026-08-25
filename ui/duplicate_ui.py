import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from utils.config import get_setting, update_setting
from tools.duplicates import run_duplicate_analysis
from ui.help_dialog import show_help_dialog

class DuplicateFrame(ctk.CTkFrame):
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
            text="Duplicate Finder", 
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
            text="Analyze a file to strip out duplicate rows. Saves a cleaned file and a log of removed duplicate entries.",
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
            text="Remove Duplicates", 
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
        content = (
            "DUPLICATE FINDER\n"
            "Scans a single file for rows that are repeated, and produces a "
            "cleaned copy plus a log of what was removed.\n\n"
            "WHAT TO UPLOAD\n"
            "- One file. Supported formats: .xlsx, .csv, .txt\n\n"
            "HEADER ROW\n"
            "- Check \"File includes a header row\" if the first row is "
            "column titles, not data.\n"
            "- Leave it unchecked if the file starts straight with data.\n"
            "- If this is set wrong on a headerless file, the first real "
            "row of data gets silently treated as a header and disappears "
            "from the results.\n\n"
            "WHAT COUNTS AS A DUPLICATE\n"
            "- A row must match COMPLETELY (every column) to be treated as "
            "a repeat.\n"
            "- Leading/trailing spaces are ignored. Capitalization matters.\n\n"
            "WHAT YOU GET\n"
            "- _CLEANED: the file with duplicates removed (the first "
            "occurrence of each entry is kept).\n"
            "- _DUPLICATES_LOG: shows each duplicated entry and how many "
            "times it was repeated. Only created if duplicates were "
            "actually found.\n"
            "- Both are saved next to the original, in the same format."
        )
        show_help_dialog(self, "How to Use: Duplicate Finder", content)

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.get_initial_dir(),
            title="Select File to Clean",
            filetypes=[("Data files", "*.xlsx *.xls *.csv *.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.input_file_path = file_path
            self.lbl_file.configure(text=os.path.basename(file_path), text_color=("black", "white"))
            update_setting("last_opened_folder", os.path.dirname(file_path))

    def execute_tool(self):
        if not self.input_file_path:
            messagebox.showerror("Error", "Please select a file to process before running.")
            return

        self.btn_run.configure(state="disabled", text="Processing...")
        self.update()

        try:
            saved_clean, saved_dup = run_duplicate_analysis(
                self.input_file_path,
                has_header=self.has_header_var.get()
            )
            
            # Construct intelligent success feedback
            msg_parts = ["Separation complete!\n"]
            msg_parts.append(f"• Cleaned output: {os.path.basename(saved_clean)}")
            
            if saved_dup:
                msg_parts.append(f"• Duplicates log: {os.path.basename(saved_dup)}")
            else:
                msg_parts.append("• No duplicate entries were found (No log was created).")
                
            msg_parts.append(f"\nSaved in directory:\n{os.path.dirname(self.input_file_path)}")
            
            messagebox.showinfo("Success!", "\n".join(msg_parts))
            
        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred:\n\n{str(e)}")
        finally:
            self.btn_run.configure(state="normal", text="Remove Duplicates")
            