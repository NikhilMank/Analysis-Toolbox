import customtkinter as ctk
from utils.config import get_setting
from ui.difference_ui import DifferenceFrame  # <-- Imports UI for Difference tool
from ui.duplicate_ui import DuplicateFrame    # <-- Imports UI for Duplicate tool

# Set the overall visual style of the application
ctk.set_appearance_mode(get_setting("theme"))  # Reads "System", "Dark", or "Light"
ctk.set_default_color_theme("blue")            # Modern blue accent color

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. Configure Main Window
        self.title("Analysis Toolbox")
        self.geometry("900x600")
        self.minsize(800, 500)

        # Configure a 1x2 grid layout (Sidebar vs. Content Area)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 2. Create the Sidebar Frame
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)  # Pushes bottom elements down

        # Sidebar Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Toolbox", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=20)

        # Navigation Buttons
        self.home_button = ctk.CTkButton(
            self.sidebar_frame, text="Home", 
            fg_color="transparent", text_color=("gray10", "gray90"), 
            hover_color=("gray70", "gray30"), anchor="w",
            command=self.show_home
        )
        self.home_button.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.diff_button = ctk.CTkButton(
            self.sidebar_frame, text="Difference Finder", 
            fg_color="transparent", text_color=("gray10", "gray90"), 
            hover_color=("gray70", "gray30"), anchor="w",
            command=self.show_difference_finder
        )
        self.diff_button.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.dup_button = ctk.CTkButton(
            self.sidebar_frame, text="Duplicate Finder", 
            fg_color="transparent", text_color=("gray10", "gray90"), 
            hover_color=("gray70", "gray30"), anchor="w",
            command=self.show_duplicate_finder
        )
        self.dup_button.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        # 3. Create Content Frames (Wired up to our real custom DifferenceFrame class!)
        self.home_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.diff_frame = DifferenceFrame(self)     # Inserting Difference Frame
        self.dup_frame = DuplicateFrame(self)       # Inserting Duplicate Frame

        # Populate ONLY our remaining placeholders (No longer touching diff_frame)
        self.setup_placeholders()

        # 4. Initialize default view
        self.show_home()

    def setup_placeholders(self):
        """Sets up temporary layouts inside our frames for initial testing."""
        # Home Placeholder
        home_label = ctk.CTkLabel(self.home_frame, text="Welcome to the Analysis Toolbox", font=ctk.CTkFont(size=24, weight="bold"))
        home_label.pack(pady=40, padx=20)
        home_sub = ctk.CTkLabel(self.home_frame, text="Select a tool from the sidebar to get started.", font=ctk.CTkFont(size=14))
        home_sub.pack(pady=10, padx=20)

        # Duplicate Finder Placeholder (Stays as placeholder until we build its real class next)
        # dup_label = ctk.CTkLabel(self.dup_frame, text="Duplicate Finder Placeholder", font=ctk.CTkFont(size=24, weight="bold"))
        # dup_label.pack(pady=40, padx=20)

    def select_frame_by_name(self, name):
        """Manages highlighting the correct button and displaying the active frame."""
        # Reset all button backgrounds to look transparent/unselected
        self.home_button.configure(fg_color="transparent")
        self.diff_button.configure(fg_color="transparent")
        self.dup_button.configure(fg_color="transparent")

        # Hide all frames
        self.home_frame.grid_forget()
        self.diff_frame.grid_forget()
        self.dup_frame.grid_forget()

        # Show the chosen frame and highlight its button
        if name == "home":
            self.home_frame.grid(row=0, column=1, sticky="nsew")
            self.home_button.configure(fg_color=("gray75", "gray25"))
        elif name == "difference":
            self.diff_frame.grid(row=0, column=1, sticky="nsew")
            self.diff_button.configure(fg_color=("gray75", "gray25"))
        elif name == "duplicates":
            self.dup_frame.grid(row=0, column=1, sticky="nsew")
            self.dup_button.configure(fg_color=("gray75", "gray25"))

    def show_home(self):
        self.select_frame_by_name("home")

    def show_difference_finder(self):
        self.select_frame_by_name("difference")

    def show_duplicate_finder(self):
        self.select_frame_by_name("duplicates")