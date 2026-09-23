import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from utils.config import get_setting, update_setting

# We will import your actual processing tool
# (We will wrap your tool's function to match this import in Step 2)
from tools.difference import run_difference_analysis
from ui.help_dialog import show_help_dialog

class DifferenceFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        
        self.file_a_path = ""
        self.file_b_path = ""
        self.has_header_var = ctk.BooleanVar(value=False)

        # Layout Configuration (1 column, multiple rows)
        self.grid_columnconfigure(0, weight=1)

        # 1. Title (with "How to Use" button alongside it)
        self.title_row = ctk.CTkFrame(self, fg_color="transparent")
        self.title_row.grid(row=0, column=0, padx=40, pady=(40, 20), sticky="ew")
        self.title_row.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.title_row, 
            text="Difference Finder", 
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
            text="Compare two Excel or CSV files. Finds rows unique to File A and unique to File B.",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.desc_label.grid(row=1, column=0, padx=40, pady=(0, 30), sticky="w")

        # 2. File A Selector Group
        self.file_a_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_a_frame.grid(row=2, column=0, padx=40, pady=10, sticky="ew")
        self.file_a_frame.grid_columnconfigure(1, weight=1)

        self.btn_browse_a = ctk.CTkButton(
            self.file_a_frame, text="Select File A", width=120, command=self.browse_file_a
        )
        self.btn_browse_a.grid(row=0, column=0, padx=(0, 10), pady=5)

        self.lbl_file_a = ctk.CTkLabel(
            self.file_a_frame, text="No file selected...", anchor="w", text_color="gray"
        )
        self.lbl_file_a.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 3. File B Selector Group
        self.file_b_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_b_frame.grid(row=3, column=0, padx=40, pady=10, sticky="ew")
        self.file_b_frame.grid_columnconfigure(1, weight=1)

        self.btn_browse_b = ctk.CTkButton(
            self.file_b_frame, text="Select File B", width=120, command=self.browse_file_b
        )
        self.btn_browse_b.grid(row=0, column=0, padx=(0, 10), pady=5)

        self.lbl_file_b = ctk.CTkLabel(
            self.file_b_frame, text="No file selected...", anchor="w", text_color="gray"
        )
        self.lbl_file_b.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 4. Header Option - user decides per run whether the files have a header row
        self.chk_has_header = ctk.CTkCheckBox(
            self,
            text="Files include a header row (first row is column titles, not data)",
            variable=self.has_header_var,
            onvalue=True,
            offvalue=False
        )
        self.chk_has_header.grid(row=4, column=0, padx=40, pady=(10, 0), sticky="w")

        # 5. Action Button (Run)
        self.btn_run = ctk.CTkButton(
            self, 
            text="Run Comparison", 
            fg_color="#2c8558",    # Forest green for action
            hover_color="#216341", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self.execute_tool
        )
        self.btn_run.grid(row=5, column=0, padx=40, pady=40, sticky="w")

    def get_initial_dir(self):
        """Helper to fetch last-used directory from configuration."""
        last_dir = get_setting("last_opened_folder")
        if os.path.exists(last_dir):
            return last_dir
        return os.path.expanduser("~")

    def show_help(self):
        show_help_dialog(self, "difference")

    def browse_file_a(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.get_initial_dir(),
            title="Select File A",
            filetypes=[("Excel or CSV files", "*.xlsx *.xls *.csv *.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.file_a_path = file_path
            self.lbl_file_a.configure(text=os.path.basename(file_path), text_color=("black", "white"))
            # Save parent directory to settings so app remembers it next time
            update_setting("last_opened_folder", os.path.dirname(file_path))

    def browse_file_b(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.get_initial_dir(),
            title="Select File B",
            filetypes=[("Excel or CSV files", "*.xlsx *.xls *.csv *.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.file_b_path = file_path
            self.lbl_file_b.configure(text=os.path.basename(file_path), text_color=("black", "white"))
            update_setting("last_opened_folder", os.path.dirname(file_path))

    def execute_tool(self):
        """Validates inputs, triggers the backend script, and displays intelligent notifications."""
        if not self.file_a_path or not self.file_b_path:
            messagebox.showerror("Error", "Please select both File A and File B before running.")
            return

        # Visual feedback: disable button during processing
        self.btn_run.configure(state="disabled", text="Processing...")
        self.update()  # Force GUI refresh

        try:
            # Call your robust comparison script, passing along the header choice
            saved_a, count_a, saved_b, count_b = run_difference_analysis(
                self.file_a_path,
                self.file_b_path,
                has_header=self.has_header_var.get()
            )

            # Construct a dynamic success message
            if not saved_a and not saved_b:
                messagebox.showinfo(
                    "Success!",
                    "Both files match perfectly!\nNo differences found, so no reports were generated."
                )
            else:
                msg_parts = ["Comparison complete!\n"]
                if saved_a:
                    msg_parts.append(f"• Unique to A: {os.path.basename(saved_a)} ({count_a:,} entries)")
                if saved_b:
                    msg_parts.append(f"• Unique to B: {os.path.basename(saved_b)} ({count_b:,} entries)")
                
                msg_parts.append(f"\nSaved in directory:\n{os.path.dirname(self.file_a_path)}")
                
                messagebox.showinfo("Success!", "\n".join(msg_parts))
                
        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred during comparison:\n\n{str(e)}")
        finally:
            # Re-enable button
            self.btn_run.configure(state="normal", text="Run Comparison")
            