import os
import customtkinter as ctk
from tkinter import filedialog
from utils.config import get_setting, update_setting
from tools.packet_matcher import run_packet_matching
from ui.help_dialog import show_help_dialog
from ui.message_dialog import show_info, show_error
from ui.ui_text import UI_TEXT

STRINGS = UI_TEXT["packet_matcher"]
OUT_OF_RANGE_CODES = ["extend", "extra_packets"]


class PacketMatcherFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")

        self.a_list_path = ""
        self.b_file_path = ""
        self._current_lang = "en"

        self.grid_columnconfigure(0, weight=1)
        # Row 0 (the scrollable form) expands; row 1 (the Run button) stays an
        # always-visible footer - same layout as PacketGeneratorFrame.
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
            text="Packet Matcher",
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
            text="Reuse the date ranges of an existing packet list (A) to build a packet list for another date file (B).",
            font=ctk.CTkFont(size=13),
            text_color="gray",
            wraplength=480,
            justify="left"
        )
        self.desc_label.grid(row=1, column=0, padx=40, pady=(0, 30), sticky="w")

        # 2. A packet list picker
        self.a_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.a_frame.grid(row=2, column=0, padx=40, pady=10, sticky="ew")
        self.a_frame.grid_columnconfigure(1, weight=1)

        self.btn_browse_a = ctk.CTkButton(
            self.a_frame, text="Select A Packet List", width=160, command=self.browse_a_list
        )
        self.btn_browse_a.grid(row=0, column=0, padx=(0, 10), pady=5)

        self.lbl_a = ctk.CTkLabel(
            self.a_frame, text="No file selected...", anchor="w", text_color="gray"
        )
        self.lbl_a.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 3. B date file picker
        self.b_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.b_frame.grid(row=3, column=0, padx=40, pady=10, sticky="ew")
        self.b_frame.grid_columnconfigure(1, weight=1)

        self.btn_browse_b = ctk.CTkButton(
            self.b_frame, text="Select B Date File", width=160, command=self.browse_b_file
        )
        self.btn_browse_b.grid(row=0, column=0, padx=(0, 10), pady=5)

        self.lbl_b = ctk.CTkLabel(
            self.b_frame, text="No file selected...", anchor="w", text_color="gray"
        )
        self.lbl_b.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 4. Out-of-range handling
        self.range_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.range_frame.grid(row=4, column=0, padx=40, pady=(10, 0), sticky="ew")

        self.lbl_range = ctk.CTkLabel(self.range_frame, text="B dates outside A:", width=120, anchor="w")
        self.lbl_range.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        # out_of_range_code is the literal value passed to run_packet_matching;
        # out_of_range_var only holds this language's DISPLAYED label for it
        # (same pattern as the Packet Generator's granularity dropdown).
        self.out_of_range_code = "extend"
        self.out_of_range_var = ctk.StringVar(value=STRINGS["out_of_range_values"]["extend"]["en"])
        self.option_range = ctk.CTkOptionMenu(
            self.range_frame,
            values=[STRINGS["out_of_range_values"][code]["en"] for code in OUT_OF_RANGE_CODES],
            variable=self.out_of_range_var,
            command=self.on_out_of_range_change,
            width=220
        )
        self.option_range.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.range_note_label = ctk.CTkLabel(
            self.scroll_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=480,
            justify="left"
        )
        self.range_note_label.grid(row=5, column=0, padx=40, pady=(2, 10), sticky="w")

        # 5. Sample Value / Its Date (optional pair, for ambiguous B formats)
        self.sample_note_label = ctk.CTkLabel(
            self.scroll_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=480,
            justify="left"
        )
        self.sample_note_label.grid(row=6, column=0, padx=40, pady=(15, 0), sticky="w")

        self.sample_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.sample_frame.grid(row=7, column=0, padx=40, pady=(5, 20), sticky="ew")

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

        # 6. Run button, outside the scrollable area so it is always visible
        self.btn_run = ctk.CTkButton(
            self,
            text="Match Packets",
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
        show_help_dialog(self, "packet_matcher")

    def on_out_of_range_change(self, name):
        labels = STRINGS["out_of_range_values"]
        for code in OUT_OF_RANGE_CODES:
            if labels[code][self._current_lang] == name:
                self.out_of_range_code = code
                return

    def apply_language(self, lang):
        self._current_lang = lang
        self.title_label.configure(text=STRINGS["title"][lang])
        self.btn_help.configure(text=STRINGS["how_to_use_button"][lang])
        self.desc_label.configure(text=STRINGS["description"][lang])
        self.btn_browse_a.configure(text=STRINGS["select_a_list"][lang])
        self.btn_browse_b.configure(text=STRINGS["select_b_file"][lang])
        if not self.a_list_path:
            self.lbl_a.configure(text=STRINGS["no_file_selected"][lang])
        if not self.b_file_path:
            self.lbl_b.configure(text=STRINGS["no_file_selected"][lang])
        self.lbl_range.configure(text=STRINGS["out_of_range_label"][lang])

        labels = STRINGS["out_of_range_values"]
        self.option_range.configure(values=[labels[code][lang] for code in OUT_OF_RANGE_CODES])
        self.out_of_range_var.set(labels[self.out_of_range_code][lang])

        self.range_note_label.configure(text=STRINGS["out_of_range_note"][lang])
        self.sample_note_label.configure(text=STRINGS["sample_note"][lang])
        self.lbl_sample_timestamp.configure(text=STRINGS["sample_value_label"][lang])
        self.entry_sample_timestamp.configure(placeholder_text=STRINGS["sample_value_placeholder"][lang])
        self.lbl_sample_date.configure(text=STRINGS["sample_date_label"][lang])
        self.entry_sample_date.configure(placeholder_text=STRINGS["date_placeholder_optional"][lang])
        if self.btn_run.cget("state") == "disabled":
            self.btn_run.configure(text=STRINGS["processing"][lang])
        else:
            self.btn_run.configure(text=STRINGS["run_button"][lang])

    def browse_a_list(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.get_initial_dir(),
            title="Select A Packet List",
            filetypes=[("Excel files", "*.xlsx"), ("All Files", "*.*")]
        )
        if file_path:
            self.a_list_path = file_path
            self.lbl_a.configure(text=os.path.basename(file_path), text_color=("black", "white"))
            update_setting("last_opened_folder", os.path.dirname(file_path))

    def browse_b_file(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.get_initial_dir(),
            title="Select B Date File",
            filetypes=[("Text files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.b_file_path = file_path
            self.lbl_b.configure(text=os.path.basename(file_path), text_color=("black", "white"))
            update_setting("last_opened_folder", os.path.dirname(file_path))

    def execute_tool(self):
        if not self.a_list_path or not self.b_file_path:
            show_error(self, "Error", "Please select both the A packet list and the B date file before running.")
            return

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
            saved_path, warnings = run_packet_matching(
                self.a_list_path,
                self.b_file_path,
                out_of_range=self.out_of_range_code,
                sample_timestamp=sample_timestamp,
                sample_timestamp_date=sample_timestamp_date
            )

            msg_parts = ["Packet report generated!\n"]
            msg_parts.append(f"• Saved as: {os.path.basename(saved_path)}")
            msg_parts.append(f"\nSaved in directory:\n{os.path.dirname(self.b_file_path)}")
            if warnings:
                msg_parts.append("\nWarnings:")
                msg_parts.extend(f"• {w}" for w in warnings)
            show_info(self, "Success!", "\n".join(msg_parts))

        except Exception as e:
            show_error(self, "Processing Error", f"An error occurred:\n\n{str(e)}")
        finally:
            self.btn_run.configure(state="normal", text=STRINGS["run_button"][self._current_lang])
