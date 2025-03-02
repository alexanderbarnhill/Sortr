from glob import glob
import shutil
from PIL import Image, ImageTk
import logging
from datetime import datetime
import tkinter as tk
from io import BytesIO
import os
from argparse import Namespace
from tkinter import scrolledtext, messagebox, Toplevel, Label, Entry, Button
import threading

log_filename = f"finwave_pipeline_image_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure log to file and stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def get_images(directory):
    extension_list = ['jpg', 'jpeg', 'JPG', 'JPEG', 'png', 'PNG']
    images = []
    for extension in extension_list:
        images.extend(glob(directory + '/**/*.' + extension, recursive=True))
    images = sorted(list(set(images)))
    return images


def move(f, t):
    shutil.move(f, t)


def open_file(f):
    img = Image.open(f)
    return img


settings = {
    "input_directory": "",
    "output_directory": "",
}

class SortrGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sortr")
        self.root.geometry("400x400")

        self.log_display = scrolledtext.ScrolledText(root, state='disabled', height=15)
        self.log_display.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.is_running = False  # To track if pipeline is running
        self.thread = None  # To hold the pipeline thread

        self.start_button = tk.Button(root, text="Start", command=self.toggle_pipeline)
        self.start_button.pack(pady=5)

        self.settings_button = tk.Button(root, text="Settings", command=self.open_settings)
        self.settings_button.pack(pady=5)

        # Redirect log to the GUI
        self.setup_logging()

    def toggle_pipeline(self):
        if not self.is_running:
            logger.info("Starting pipeline")
            self.is_running = True
            self.start_button.config(text="Stop")  # Change button text to Stop
            self.thread = threading.Thread(target=self.start_pipeline)
            self.thread.start()  # Start the pipeline in a new thread
        else:
            logger.info("Stopping pipeline")
            self.is_running = False
            self.start_button.config(text="Start Pipeline")  # Change button text back to Start
            # Optionally, signal the pipeline thread to stop here if needed

    def start_pipeline(self):
        logger.info(f"Starting pipeline with settings: {settings}")
        logger.info("Step 1: Data loading...")
        args = Namespace(**settings)
        images = get_images(args.input_directory)
        logger.info(f"Found {len(images)} images")
        for idx, path in list(enumerate(images)):
            if not self.is_running:
                logger.info("Pipeline stopped.")
                break
            logger.info(f"[{idx + 1} \t / \t {len(images)}] Processing {path}")
            self.process_image(path, args)

    def process_image(self, path, args):
        img = open_file(path)

        valid_keys = {'y', 'm', 'n'}
        user_input = None

        def on_key(event):
            nonlocal user_input
            if event.char in valid_keys:
                user_input = event.char
                image_window.destroy()

        def resize_image(event):
            # Scale the image to fit the window size without rotating vertical images
            resized_img = img.copy()
            img_width, img_height = resized_img.size
            screen_width = event.width
            screen_height = event.height

            # If the image is portrait (height > width), scale it to fit vertically
            if img_width > img_height:
                resized_img.thumbnail((screen_width, screen_height), Image.Resampling.LANCZOS)
            else:
                # For portrait images, preserve the height and adjust the width proportionally
                resized_img.thumbnail((min(screen_width, img_width), min(screen_height, img_height)),
                                      Image.Resampling.LANCZOS)

            img_tk = ImageTk.PhotoImage(resized_img)
            label.config(image=img_tk)
            label.image = img_tk

        def undo_action():
            logger.info("Undoing last action")

        def previous_image():
            logger.info("Going back to previous image")

        def next_image():
            logger.info("Skipping to next image")

        def exit_processing():
            logger.info("Exiting image processing")
            self.is_running = False
            image_window.destroy()

        # Convert image for Tkinter
        img = img.convert("RGB")

        # Create a new full-screen window with the image and key bindings
        image_window = tk.Toplevel(self.root)
        image_window.title("Image Review")
        image_window.attributes('-fullscreen', True)

        # Button row at the top of the image frame
        button_frame = tk.Frame(image_window)
        button_frame.pack(side=tk.TOP, fill=tk.X)

        exit_button = tk.Button(button_frame, text="Exit", command=exit_processing)
        exit_button.pack(side=tk.LEFT, padx=10)

        # Initial display of the image without rotating vertical images
        resized_img = img.copy()
        img_width, img_height = resized_img.size
        screen_width = image_window.winfo_screenwidth()
        screen_height = image_window.winfo_screenheight()

        # Adjust scaling based on the orientation of the image (portrait or landscape)
        if img_width > img_height:
            resized_img.thumbnail((screen_width, screen_height), Image.Resampling.LANCZOS)
        else:
            resized_img.thumbnail((min(screen_width, img_width), min(screen_height, img_height)),
                                  Image.Resampling.LANCZOS)

        img_tk = ImageTk.PhotoImage(resized_img)

        label = tk.Label(image_window, image=img_tk)
        label.image = img_tk
        label.pack(expand=True, fill=tk.BOTH)

        instruction = tk.Label(image_window, text="Press 'y', 'm', or 'n'", bg='white')
        instruction.pack(pady=10)

        image_window.bind('<Key>', on_key)
        image_window.bind('<Configure>', resize_image)
        image_window.focus_force()

        # Wait for user input
        while user_input not in valid_keys and self.is_running:
            self.root.update()

        if user_input == 'y':
            logger.info(f"User confirmed 'yes' for {path}")
        elif user_input == 'm':
            logger.info(f"User selected 'maybe' for {path}")
        elif user_input == 'n':
            logger.info(f"User rejected 'no' for {path}")

        logger.info(f"Image processing complete for {path}")
        self.handle_user_selection(path, user_input, args)

    def handle_user_selection(self, f, choice, args):
        output_directory = args.output_directory if args.output_directory else args.input_directory

        out = "Yes" if choice == "y" else "No" if choice == "n" else "Maybe"
        out_folder = os.path.join(output_directory, out)
        os.makedirs(out_folder, exist_ok=True)

        move(f, out_folder)
    def setup_logging(self):
        class TextHandler(logging.Handler):
            def __init__(self, widget):
                super().__init__()
                self.widget = widget

            def emit(self, record):
                msg = self.format(record)
                self.widget.config(state='normal')
                self.widget.insert(tk.END, msg + '\n')
                self.widget.config(state='disabled')
                self.widget.yview(tk.END)

        text_handler = TextHandler(self.log_display)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(text_handler)
        logger.propagate = False

    def open_settings(self):
        settings_window = Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("600x600")

        entries = {}

        for i, (key, value) in enumerate(settings.items()):
            Label(settings_window, text=key).grid(row=i, column=0, padx=10, pady=5, sticky='w')
            entry = Entry(settings_window)
            entry.insert(0, str(value))
            entry.grid(row=i, column=1, padx=10, pady=5)
            entries[key] = entry

        def save_settings():
            logger.info("Saving settings")
            for key, entry in entries.items():
                new_value = entry.get()
                if isinstance(settings[key], bool):
                    settings[key] = new_value.lower() in ('true', '1', 'yes')
                elif isinstance(settings[key], int):
                    try:
                        settings[key] = int(new_value)
                    except ValueError:
                        messagebox.showerror("Invalid input", f"{key} must be an integer")
                        return
                else:
                    settings[key] = new_value
            settings_window.destroy()

        Button(settings_window, text="Save", command=save_settings).grid(row=len(settings), columnspan=2, pady=10)

if __name__ == '__main__':
    root = tk.Tk()
    app = SortrGUI(root)
    root.mainloop()