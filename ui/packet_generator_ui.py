import os
import customtkinter as ctk
from tkinter import filedialog
from utils.config import get_setting, update_setting
from tools.packet_generator import run_packet_generation
from ui.help_dialog import show_help_dialog
from ui.message_dialog import show_info, show_error
from ui.ui_text import UI_TEXT

STRINGS = UI_TEXT["packet_generator"]
GRANULARITY_CODES = ["year", "half-year", "quarter", "month", "day"]
FINEST_GRANULARITY_CODES = ["half-year", "quarter", "month", "day"]
GRANULARITY_ORDER = ["year", "half-year", "quarter", "month", "day"]  # coarse -> fine


class PacketGeneratorFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")

        self.input_file_path = ""
        self._current_lang = "en"

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
            text_color="gray",
            wraplength=480,
            justify="left"
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

        # granularity_code is the literal value passed to run_packet_generation;
        # granularity_var only ever holds this language's DISPLAYED label for it,
        # since the two can differ once the dropdown is translated (see
        # on_granularity_change / apply_language).
        self.granularity_code = "year"
        self.granularity_var = ctk.StringVar(value=STRINGS["granularity_values"]["year"]["en"])
        self.option_granularity = ctk.CTkOptionMenu(
            self.granularity_frame,
            values=[STRINGS["granularity_values"][code]["en"] for code in GRANULARITY_CODES],
            variable=self.granularity_var,
            command=self.on_granularity_change,
            width=200
        )
        self.option_granularity.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 3d. Finest Granularity
        self.finest_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.finest_frame.grid(row=6, column=0, padx=40, pady=(0, 0), sticky="ew")

        self.lbl_finest = ctk.CTkLabel(self.finest_frame, text="Finest Granularity:", width=120, anchor="w")
        self.lbl_finest.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        # Same code-vs-displayed-label split as the start granularity above.
        self.finest_code = "day"
        self.finest_var = ctk.StringVar(value=STRINGS["finest_granularity_values"]["day"]["en"])
        self.option_finest = ctk.CTkOptionMenu(
            self.finest_frame,
            values=[STRINGS["finest_granularity_values"][code]["en"] for code in FINEST_GRANULARITY_CODES],
            variable=self.finest_var,
            command=self.on_finest_change,
            width=200
        )
        self.option_finest.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.finest_note_label = ctk.CTkLabel(
            self.scroll_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=480,
            justify="left"
        )
        self.finest_note_label.grid(row=7, column=0, padx=40, pady=(0, 10), sticky="w")

        # 4. Start Date (optional)
        self.start_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.start_frame.grid(row=8, column=0, padx=40, pady=10, sticky="ew")

        self.lbl_start = ctk.CTkLabel(self.start_frame, text="Start Date:", width=120, anchor="w")
        self.lbl_start.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.entry_start = ctk.CTkEntry(self.start_frame, placeholder_text="DD.MM.YYYY (optional)", width=200)
        self.entry_start.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 5. End Date (optional)
        self.end_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.end_frame.grid(row=9, column=0, padx=40, pady=10, sticky="ew")

        self.lbl_end = ctk.CTkLabel(self.end_frame, text="End Date:", width=120, anchor="w")
        self.lbl_end.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.entry_end = ctk.CTkEntry(self.end_frame, placeholder_text="DD.MM.YYYY (optional)", width=200)
        self.entry_end.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 5b. Build direction
        self.direction_var = ctk.BooleanVar(value=False)
        self.chk_direction = ctk.CTkCheckBox(
            self.scroll_frame,
            text="Build backward",
            variable=self.direction_var,
            onvalue=True,
            offvalue=False
        )
        self.chk_direction.grid(row=10, column=0, padx=40, pady=(10, 0), sticky="w")

        self.direction_note_label = ctk.CTkLabel(
            self.scroll_frame,
            text="Unchecked (default): builds oldest-to-newest, and the leftover packet that doesn't fit "
                 "evenly is the most recent data. Checked: builds newest-to-oldest instead, so the "
                 "leftover packet becomes the oldest data.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=480,
            justify="left"
        )
        self.direction_note_label.grid(row=11, column=0, padx=40, pady=(2, 10), sticky="w")

        # 6. Sample Timestamp / Sample Date (optional pair, for ambiguous formats)
        self.sample_note_label = ctk.CTkLabel(
            self.scroll_frame,
            text="If the file's format is unusual or ambiguous, give one real example instead of guessing:",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=480,
            justify="left"
        )
        self.sample_note_label.grid(row=12, column=0, padx=40, pady=(15, 0), sticky="w")

        self.sample_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.sample_frame.grid(row=13, column=0, padx=40, pady=(5, 20), sticky="ew")

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

    def on_granularity_change(self, name):
        labels = STRINGS["granularity_values"]
        for code in GRANULARITY_CODES:
            if labels[code][self._current_lang] == name:
                self.granularity_code = code
                return

    def on_finest_change(self, name):
        labels = STRINGS["finest_granularity_values"]
        for code in FINEST_GRANULARITY_CODES:
            if labels[code][self._current_lang] == name:
                self.finest_code = code
                return

    def apply_language(self, lang):
        self._current_lang = lang
        self.title_label.configure(text=STRINGS["title"][lang])
        self.btn_help.configure(text=STRINGS["how_to_use_button"][lang])
        self.desc_label.configure(text=STRINGS["description"][lang])
        self.btn_browse.configure(text=STRINGS["select_file"][lang])
        if not self.input_file_path:
            self.lbl_file.configure(text=STRINGS["no_file_selected"][lang])
        self.lbl_size.configure(text=STRINGS["packet_size_label"][lang])
        self.entry_size.configure(placeholder_text=STRINGS["packet_size_placeholder"][lang])
        self.lbl_tolerance.configure(text=STRINGS["tolerance_label"][lang])
        self.entry_tolerance.configure(placeholder_text=STRINGS["tolerance_placeholder"][lang])
        self.lbl_granularity.configure(text=STRINGS["granularity_label"][lang])

        labels = STRINGS["granularity_values"]
        self.option_granularity.configure(values=[labels[code][lang] for code in GRANULARITY_CODES])
        self.granularity_var.set(labels[self.granularity_code][lang])

        self.lbl_finest.configure(text=STRINGS["finest_granularity_label"][lang])
        finest_labels = STRINGS["finest_granularity_values"]
        self.option_finest.configure(values=[finest_labels[code][lang] for code in FINEST_GRANULARITY_CODES])
        self.finest_var.set(finest_labels[self.finest_code][lang])
        self.finest_note_label.configure(text=STRINGS["finest_granularity_note"][lang])

        self.lbl_start.configure(text=STRINGS["start_date_label"][lang])
        self.entry_start.configure(placeholder_text=STRINGS["date_placeholder_optional"][lang])
        self.lbl_end.configure(text=STRINGS["end_date_label"][lang])
        self.entry_end.configure(placeholder_text=STRINGS["date_placeholder_optional"][lang])
        self.chk_direction.configure(text=STRINGS["direction_checkbox"][lang])
        self.direction_note_label.configure(text=STRINGS["direction_note"][lang])
        self.sample_note_label.configure(text=STRINGS["sample_note"][lang])
        self.lbl_sample_timestamp.configure(text=STRINGS["sample_value_label"][lang])
        self.entry_sample_timestamp.configure(placeholder_text=STRINGS["sample_value_placeholder"][lang])
        self.lbl_sample_date.configure(text=STRINGS["sample_date_label"][lang])
        self.entry_sample_date.configure(placeholder_text=STRINGS["date_placeholder_optional"][lang])
        if self.btn_run.cget("state") == "disabled":
            self.btn_run.configure(text=STRINGS["processing"][lang])
        else:
            self.btn_run.configure(text=STRINGS["run_button"][lang])

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
            show_error(self, "Error", "Please select a date file before running.")
            return

        size_text = self.entry_size.get().strip()
        if not size_text:
            show_error(self, "Error", "Please enter a Packet Size (N) before running.")
            return
        try:
            packet_size = int(size_text)
            if packet_size <= 0:
                raise ValueError
        except ValueError:
            show_error(self, "Error", "Packet Size (N) must be a positive whole number.")
            return

        tolerance_text = self.entry_tolerance.get().strip()
        if not tolerance_text:
            show_error(self, "Error", "Please enter a Tolerance % before running.")
            return
        try:
            tolerance_percent = float(tolerance_text)
            if tolerance_percent < 0:
                raise ValueError
        except ValueError:
            show_error(self, "Error", "Tolerance % must be a non-negative number (e.g. 20).")
            return

        start_date = self.entry_start.get().strip() or None
        end_date = self.entry_end.get().strip() or None
        start_granularity = self.granularity_code
        finest_granularity = self.finest_code
        if GRANULARITY_ORDER.index(finest_granularity) < GRANULARITY_ORDER.index(start_granularity):
            show_error(
                self,
                "Error",
                f"Finest Granularity ({finest_granularity}) cannot be coarser than Start Granularity "
                f"({start_granularity}). Choose a Start Granularity of {finest_granularity} or coarser."
            )
            return
        direction = 'backward' if self.direction_var.get() else 'forward'

        sample_timestamp = self.entry_sample_timestamp.get().strip() or None
        sample_timestamp_date = self.entry_sample_date.get().strip() or None
        if (sample_timestamp is None) != (sample_timestamp_date is None):
            show_error(self,
                "Error", "Sample Value and Its Date must both be filled in, or both left blank."
            )
            return

        self.btn_run.configure(state="disabled", text=STRINGS["processing"][self._current_lang])
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
                finest_granularity=finest_granularity,
                direction=direction
            )

            if not saved_path:
                msg = "No packets were generated.\n"
                if warnings:
                    msg += "\n" + "\n".join(f"• {w}" for w in warnings)
                show_info(self, "No Data", msg)
            else:
                msg_parts = ["Packet report generated!\n"]
                msg_parts.append(f"• Saved as: {os.path.basename(saved_path)}")
                msg_parts.append(f"\nSaved in directory:\n{os.path.dirname(self.input_file_path)}")
                if warnings:
                    msg_parts.append("\nWarnings:")
                    msg_parts.extend(f"• {w}" for w in warnings)
                show_info(self, "Success!", "\n".join(msg_parts))

        except Exception as e:
            show_error(self, "Processing Error", f"An error occurred:\n\n{str(e)}")
        finally:
            self.btn_run.configure(state="normal", text=STRINGS["run_button"][self._current_lang])
