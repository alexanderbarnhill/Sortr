from glob import glob
import shutil
from PIL import Image, ImageTk
import logging
from datetime import datetime
import tkinter as tk
from io import BytesIO
import cv2
import numpy as np
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

def get_sharpness(image_path):
    # Read the image
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    if img is None:
        raise ValueError(f"Unable to read the image at {image_path}")

    # Apply Laplacian operator to the image
    laplacian = cv2.Laplacian(img, cv2.CV_64F)

    # Compute the variance of the Laplacian
    sharpness = laplacian.var()

    return sharpness


def correct_image_orientation(img):
    try:
        exif = img._getexif()
        if exif is not None:
            orientation_tag = 274  # EXIF orientation tag
            orientation = exif.get(orientation_tag, None)
            logger.info(f"Orientation: {orientation}")
            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError) as e:
        logger.info(f"Could not get orientation: {e}")
        pass  # EXIF data not available or not usable
    return img

settings = {
    "input_directory": "",
    "output_directory": "",
    "sharpness_threshold": 200
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

        self.settings_button = tk.Button(root, text="Settings", command=self.open_settings)
        self.settings_button.pack(pady=5)

        self.start_button = tk.Button(root, text="Start", command=self.toggle_pipeline)
        self.start_button.pack(pady=5)

        self.settings_button = tk.Button(root, text="Filter Blurry", command=self.filter_blurry)
        self.settings_button.pack(pady=5)

        self.yes_dir = "YES"
        self.no_dir = "NO"
        self.maybe_dir = "MAYBE"

        # Redirect log to the GUI
        self.setup_logging()

    def get_blurry_directory(self, args):
        blurry_directory = self.get_output(args)
        blurry_directory = os.path.join(blurry_directory, ".too_blurry")
        return blurry_directory

    def filter_blurry(self):
        args = Namespace(**settings)
        images = get_images(args.input_directory)
        logger.info(f"Found {len(images)} images")
        blurry_directory = self.get_blurry_directory(args)
        os.makedirs(blurry_directory, exist_ok=True)
        for idx, path in list(enumerate(images)):
            sharpness = get_sharpness(path)
            logger.info(f"Path: {path}, Sharpness: {sharpness}")
            if sharpness < args.sharpness_threshold:
                logger.info(f"{path} is under sharpness threshold of {args.sharpness_threshold}. Moving to {blurry_directory}")
                shutil.move(path, blurry_directory)


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

    def filter_images(self, images, args):
        kept = []
        blurry_directory = self.get_blurry_directory(args)
        for image in images:
            if blurry_directory in image:
                continue
            if args.include_processed is True:
                # TODO
                pass
            kept.append(image)
        return kept


    def start_pipeline(self):
        logger.info(f"Starting pipeline with settings: {settings}")
        logger.info("Step 1: Data loading...")
        args = Namespace(**settings)
        images = get_images(args.input_directory)
        images = self.filter_images(images, args)
        logger.info(f"Found {len(images)} images")
        for idx, path in list(enumerate(images)):
            if not self.is_running:
                logger.info("Pipeline stopped.")
                break
            logger.info(f"[{idx + 1} \t / \t {len(images)}] Processing {path}")
            self.process_image(path, args)

    import tkinter as tk
    from PIL import Image, ImageTk

    def process_image(self, path, args):
        img = open_file(path)
        img = correct_image_orientation(img)  # Correct orientation here

        valid_keys = {'y', 'm', 'n'}
        user_input = None
        zoom_level = 1.0
        pan_x, pan_y = 0, 0

        def on_key(event):
            nonlocal user_input
            if event.char in valid_keys:
                user_input = event.char
                image_window.destroy()

        def resize_image():
            nonlocal img
            resized_img = img.copy()

            # Adjust zoom and pan
            width, height = resized_img.size
            zoomed_width = int(width * zoom_level)
            zoomed_height = int(height * zoom_level)
            resized_img = resized_img.resize((zoomed_width, zoomed_height), Image.Resampling.LANCZOS)

            # Apply pan offset
            image_x = pan_x * zoom_level
            image_y = pan_y * zoom_level

            # Adjusting the image to the pan
            resized_img = resized_img.crop((image_x, image_y, image_x + zoomed_width, image_y + zoomed_height))

            img_tk = ImageTk.PhotoImage(resized_img)
            label.config(image=img_tk)
            label.image = img_tk

        def on_mouse_wheel(event):
            logger.info("Mouse wheel detected")
            nonlocal zoom_level
            zoom_factor = 1.1

            # For Windows and Linux, event.delta might return different values. Adjust accordingly
            if event.delta > 0 or event.num == 5:  # Scroll up (zoom in)
                zoom_level /= zoom_factor
            elif event.delta < 0 or event.num == 4:  # Scroll down (zoom out)
                zoom_level *= zoom_factor

            resize_image()

        def on_mouse_drag(event):
            nonlocal pan_x, pan_y
            if event.state == 1:  # Left button pressed
                pan_x += event.x - pan_x
                pan_y += event.y - pan_y
                resize_image()

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

        def rotate_image():
            nonlocal img  # Access the original image
            img = img.rotate(90, expand=True)  # Rotate the image by 90 degrees
            resize_image()  # Resize the image to fit the window after rotation

        def anti_rotate_image():
            nonlocal img
            img = img.rotate(-90, expand=True)
            resize_image()

        # Convert image for Tkinter
        img = img.convert("RGB")

        image_window = tk.Toplevel(self.root)
        image_window.title("Image Review")
        image_window.attributes('-fullscreen', True)

        button_frame = tk.Frame(image_window)
        button_frame.pack(side=tk.TOP, fill=tk.X)

        # Create a Text widget for displaying the file name that is selectable
        file_name_text = tk.Text(button_frame, height=1, width=50, wrap=tk.WORD, font=("Arial", 14))
        file_name_text.insert(tk.END, path.split("/")[-1])  # Insert the file name
        file_name_text.config(state=tk.DISABLED)  # Make the text read-only (selectable, but not editable)
        file_name_text.pack(side=tk.TOP, pady=10)

        exit_button = tk.Button(button_frame, text="Exit", command=exit_processing)
        exit_button.pack(side=tk.LEFT, padx=10)

        anti_rotate_button = tk.Button(button_frame, text="Rotate 90° Counter Clockwise", command=anti_rotate_image)
        anti_rotate_button.pack(side=tk.LEFT, padx=10)

        rotate_button = tk.Button(button_frame, text="Rotate 90° Clockwise", command=rotate_image)
        rotate_button.pack(side=tk.LEFT, padx=10)

        # Initial display of the image
        resized_img = img.copy()
        img_width, img_height = resized_img.size
        screen_width = image_window.winfo_screenwidth()
        screen_height = image_window.winfo_screenheight()

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
        image_window.bind_all('<MouseWheel>', on_mouse_wheel)  # Ensures it works even if the window isn't focused
        image_window.bind_all('<Button-4>', on_mouse_wheel)  # Linux systems sometimes use this event
        image_window.bind_all('<Button-5>', on_mouse_wheel)  #
        image_window.focus_force()

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

    def get_output(self, args):
        output_directory = args.output_directory if args.output_directory else args.input_directory
        return output_directory

    def handle_user_selection(self, f, choice, args):
        output_directory = self.get_output(args)

        out = self.yes_dir if choice == "y" else self.no_dir if choice == "n" else self.maybe_dir
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
