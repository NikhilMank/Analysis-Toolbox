import sys
import os

# Add the root directory to python path to ensure imports work smoothly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.app import App

if __name__ == "__main__":
    # Instantiate the application and start the main loop
    app = App()
    app.mainloop()