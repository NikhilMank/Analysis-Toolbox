import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from utils.config import get_setting, update_setting
from tools.packet_generator import run_packet_generation
from ui.help_dialog import show_help_dialog


class PacketGeneratorFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")

        self.input_file_path = ""

        self.grid_columnconfigure(0, weight=1)
        # Row 0 (the scrollable form) expands; row 1 (the Run button) stays a
        # fixed-height footer that's always visible, however tall the form
        # above it grows - a plain (non-scrolling) frame can't guarantee that
        # on this app's fixed-size window, since a form with enough fields
        # can end up taller than the window and push the button off-screen
        # with no way to reach it.
        self.grid_rowconfigure(0, weight=1)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=0, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # 1. Title (with "How to Use" button alongside it)
        self.title_row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.title_row.grid(row=0, column=0, padx=40, pady=(40, 20), sticky="ew")
        self.title_row.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.title_row,
            text="Packet Generator",
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
            self.scroll_frame,
            text="Split a list of dates or timestamps into calendar-aligned packets sized close to a target record count.",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.desc_label.grid(row=1, column=0, padx=40, pady=(0, 30), sticky="w")

        # 2. File Selection Group
        self.file_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.file_frame.grid(row=2, column=0, padx=40, pady=10, sticky="ew")
        self.file_frame.grid_columnconfigure(1, weight=1)

        self.btn_browse = ctk.CTkButton(
            self.file_frame, text="Select Date File", width=120, command=self.browse_file
        )
        self.btn_browse.grid(row=0, column=0, padx=(0, 10), pady=5)

        self.lbl_file = ctk.CTkLabel(
            self.file_frame, text="No file selected...", anchor="w", text_color="gray"
        )
        self.lbl_file.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 3. Packet Size (N)
        self.size_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.size_frame.grid(row=3, column=0, padx=40, pady=10, sticky="ew")

        self.lbl_size = ctk.CTkLabel(self.size_frame, text="Packet Size (N):", width=120, anchor="w")
        self.lbl_size.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.entry_size = ctk.CTkEntry(self.size_frame, placeholder_text="e.g. 70000", width=200)
        self.entry_size.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 3b. Tolerance % (required)
        self.tolerance_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.tolerance_frame.grid(row=4, column=0, padx=40, pady=(0, 10), sticky="ew")

        self.lbl_tolerance = ctk.CTkLabel(self.tolerance_frame, text="Tolerance %:", width=120, anchor="w")
        self.lbl_tolerance.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.entry_tolerance = ctk.CTkEntry(self.tolerance_frame, placeholder_text="e.g. 20", width=200)
        self.entry_tolerance.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 3c. Start Granularity
        self.granularity_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.granularity_frame.grid(row=5, column=0, padx=40, pady=(0, 10), sticky="ew")

        self.lbl_granularity = ctk.CTkLabel(self.granularity_frame, text="Start Granularity:", width=120, anchor="w")
        self.lbl_granularity.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.granularity_var = ctk.StringVar(value="year")
        self.option_granularity = ctk.CTkOptionMenu(
            self.granularity_frame,
            values=["year", "half-year", "quarter", "month"],
            variable=self.granularity_var,
            width=200
        )
        self.option_granularity.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 4. Start Date (optional)
        self.start_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.start_frame.grid(row=6, column=0, padx=40, pady=10, sticky="ew")

        self.lbl_start = ctk.CTkLabel(self.start_frame, text="Start Date:", width=120, anchor="w")
        self.lbl_start.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.entry_start = ctk.CTkEntry(self.start_frame, placeholder_text="DD.MM.YYYY (optional)", width=200)
        self.entry_start.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 5. End Date (optional)
        self.end_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.end_frame.grid(row=7, column=0, padx=40, pady=10, sticky="ew")

        self.lbl_end = ctk.CTkLabel(self.end_frame, text="End Date:", width=120, anchor="w")
        self.lbl_end.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.entry_end = ctk.CTkEntry(self.end_frame, placeholder_text="DD.MM.YYYY (optional)", width=200)
        self.entry_end.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 5b. Build direction
        self.direction_var = ctk.BooleanVar(value=False)
        self.chk_direction = ctk.CTkCheckBox(
            self.scroll_frame,
            text="Build backward - start from the most recent date and work toward the oldest",
            variable=self.direction_var,
            onvalue=True,
            offvalue=False
        )
        self.chk_direction.grid(row=8, column=0, padx=40, pady=(10, 0), sticky="w")

        self.direction_note_label = ctk.CTkLabel(
            self.scroll_frame,
            text="Unchecked (default): builds oldest-to-newest, and the leftover packet that doesn't fit\n"
                 "evenly is the most recent data. Checked: builds newest-to-oldest instead, so the\n"
                 "leftover packet becomes the oldest data.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="left"
        )
        self.direction_note_label.grid(row=9, column=0, padx=40, pady=(2, 10), sticky="w")

        # 6. Sample Timestamp / Sample Date (optional pair, for ambiguous formats)
        self.sample_note_label = ctk.CTkLabel(
            self.scroll_frame,
            text="If the file's format is unusual or ambiguous, give one real example instead of guessing:",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.sample_note_label.grid(row=10, column=0, padx=40, pady=(15, 0), sticky="w")

        self.sample_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.sample_frame.grid(row=11, column=0, padx=40, pady=(5, 20), sticky="ew")

        self.lbl_sample_timestamp = ctk.CTkLabel(self.sample_frame, text="Sample Value:", width=120, anchor="w")
        self.lbl_sample_timestamp.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.entry_sample_timestamp = ctk.CTkEntry(
            self.sample_frame, placeholder_text="e.g. 20230115143045 (optional)", width=200
        )
        self.entry_sample_timestamp.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.lbl_sample_date = ctk.CTkLabel(self.sample_frame, text="Its Date:", width=80, anchor="w")
        self.lbl_sample_date.grid(row=0, column=2, padx=(20, 10), pady=5, sticky="w")

        self.entry_sample_date = ctk.CTkEntry(
            self.sample_frame, placeholder_text="DD.MM.YYYY (optional)", width=160
        )
        self.entry_sample_date.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # 7. Action Button (Run) - deliberately OUTSIDE the scrollable area, in
        # the outer frame's own row 1, so it's always visible regardless of
        # scroll position or how tall the form above it is.
        self.btn_run = ctk.CTkButton(
            self,
            text="Generate Packets",
            fg_color="#2c8558",
            hover_color="#216341",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self.execute_tool
        )
        self.btn_run.grid(row=1, column=0, padx=40, pady=(10, 20), sticky="w")

    def get_initial_dir(self):
        last_dir = get_setting("last_opened_folder")
        if os.path.exists(last_dir):
            return last_dir
        return os.path.expanduser("~")

    def show_help(self):
        show_help_dialog(self, "packet_generator")

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.get_initial_dir(),
            title="Select Date File",
            filetypes=[("Text files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.input_file_path = file_path
            self.lbl_file.configure(text=os.path.basename(file_path), text_color=("black", "white"))
            update_setting("last_opened_folder", os.path.dirname(file_path))

    def execute_tool(self):
        if not self.input_file_path:
            messagebox.showerror("Error", "Please select a date file before running.")
            return

        size_text = self.entry_size.get().strip()
        if not size_text:
            messagebox.showerror("Error", "Please enter a Packet Size (N) before running.")
            return
        try:
            packet_size = int(size_text)
            if packet_size <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Packet Size (N) must be a positive whole number.")
            return

        tolerance_text = self.entry_tolerance.get().strip()
        if not tolerance_text:
            messagebox.showerror("Error", "Please enter a Tolerance % before running.")
            return
        try:
            tolerance_percent = float(tolerance_text)
            if tolerance_percent < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Tolerance % must be a non-negative number (e.g. 20).")
            return

        start_date = self.entry_start.get().strip() or None
        end_date = self.entry_end.get().strip() or None
        start_granularity = self.granularity_var.get()
        direction = 'backward' if self.direction_var.get() else 'forward'

        sample_timestamp = self.entry_sample_timestamp.get().strip() or None
        sample_timestamp_date = self.entry_sample_date.get().strip() or None
        if (sample_timestamp is None) != (sample_timestamp_date is None):
            messagebox.showerror(
                "Error", "Sample Value and Its Date must both be filled in, or both left blank."
            )
            return

        self.btn_run.configure(state="disabled", text="Processing...")
        self.update()

        try:
            saved_path, warnings = run_packet_generation(
                self.input_file_path,
                packet_size,
                tolerance_percent,
                start_date=start_date,
                end_date=end_date,
                sample_timestamp=sample_timestamp,
                sample_timestamp_date=sample_timestamp_date,
                start_granularity=start_granularity,
                direction=direction
            )

            if not saved_path:
                msg = "No packets were generated.\n"
                if warnings:
                    msg += "\n" + "\n".join(f"• {w}" for w in warnings)
                messagebox.showinfo("No Data", msg)
            else:
                msg_parts = ["Packet report generated!\n"]
                msg_parts.append(f"• Saved as: {os.path.basename(saved_path)}")
                msg_parts.append(f"\nSaved in directory:\n{os.path.dirname(self.input_file_path)}")
                if warnings:
                    msg_parts.append("\nWarnings:")
                    msg_parts.extend(f"• {w}" for w in warnings)
                messagebox.showinfo("Success!", "\n".join(msg_parts))

        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred:\n\n{str(e)}")
        finally:
            self.btn_run.configure(state="normal", text="Generate Packets")
