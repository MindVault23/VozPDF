import fitz  # PyMuPDF
import tkinter as tk
from tkinter.filedialog import askopenfilename
from tkinter import ttk
from PIL import Image, ImageTk
import pyttsx3
import threading
import json
import os

class PDFReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Reader")
        self.root.geometry("900x700")

        # Ocultar el ícono de Tkinter en la esquina superior izquierda
        self.root.iconbitmap('descarga.ico')

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', font=('Helvetica', 12))

        self.pdf_document = None
        self.current_page = 0
        self.pages_count = 0
        self.text_positions = []
        self.is_reading = False
        self.paused = False
        self.stop_reading = False
        self.fullscreen = False
        self.highlight_lines = []
        self.config_file = "reading_position.json"
        self.load_last_position = False

        self.top_frame = ttk.Frame(root, padding=(10, 10, 10, 10))
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        self.load_pdf_button = ttk.Button(self.top_frame, text="Load PDF", command=self.load_pdf)
        self.load_pdf_button.pack(side=tk.LEFT)

        self.play_button = ttk.Button(self.top_frame, text="Play", command=self.start_reading, state=tk.DISABLED)
        self.play_button.pack(side=tk.LEFT)

        self.pause_button = ttk.Button(self.top_frame, text="Pause", command=self.pause_reading, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT)

        self.resume_button = ttk.Button(self.top_frame, text="Resume", command=self.resume_reading, state=tk.DISABLED)
        self.resume_button.pack(side=tk.LEFT)

        self.prev_page_button = ttk.Button(self.top_frame, text="Prev Page", command=self.prev_page, state=tk.DISABLED)
        self.prev_page_button.pack(side=tk.LEFT)

        self.next_page_button = ttk.Button(self.top_frame, text="Next Page", command=self.next_page, state=tk.DISABLED)
        self.next_page_button.pack(side=tk.LEFT)

        self.page_entry = ttk.Entry(self.top_frame, width=5)
        self.page_entry.pack(side=tk.LEFT)
        self.page_entry.insert(0, "1")

        self.page_button = ttk.Button(self.top_frame, text="Go to Page", command=self.goto_page, state=tk.DISABLED)
        self.page_button.pack(side=tk.LEFT)

        self.play_page_button = ttk.Button(self.top_frame, text="Play Page", command=self.play_page, state=tk.DISABLED)
        self.play_page_button.pack(side=tk.LEFT)

        self.page_label = ttk.Label(self.top_frame, text="Page: 1")
        self.page_label.pack(side=tk.LEFT)

        self.fullscreen_button = ttk.Button(self.top_frame, text="Fullscreen", command=self.toggle_fullscreen)
        self.fullscreen_button.pack(side=tk.RIGHT)

        self.scroll_frame = ttk.Frame(root, padding=(10, 10, 10, 10))
        self.scroll_frame.pack(expand=True, fill=tk.BOTH)

        self.canvas = tk.Canvas(self.scroll_frame, bg="#f0f0f0")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scroll_y = ttk.Scrollbar(self.scroll_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.configure(yscrollcommand=self.scroll_y.set)
        self.canvas.bind('<Configure>', self.on_canvas_configure)

        self.player = pyttsx3.init()

    def on_canvas_configure(self, event):
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        if not self.fullscreen:
            self.root.geometry("900x700")
        self.display_page()

    def load_pdf(self):
        book = askopenfilename(title="Select a PDF file", filetypes=[("PDF files", "*.pdf")])
        if book:
            self.pdf_document = fitz.open(book)
            self.pages_count = self.pdf_document.page_count
            self.current_page = 0
            if self.load_last_position:
                self.load_reading_position()
            self.display_page()
            self.update_page_label()
            self.play_button.config(state=tk.NORMAL)
            self.page_button.config(state=tk.NORMAL)
            self.play_page_button.config(state=tk.NORMAL)
            self.prev_page_button.config(state=tk.DISABLED if self.current_page == 0 else tk.NORMAL)
            self.next_page_button.config(state=tk.DISABLED if self.current_page == self.pages_count - 1 else tk.NORMAL)

    def display_page(self):
        self.canvas.delete("all")
        page = self.pdf_document.load_page(self.current_page)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        ratio = min(canvas_width / pix.width, canvas_height / pix.height)
        new_width = int(pix.width * ratio)
        new_height = int(pix.height * ratio)

        img = img.resize((new_width, new_height), Image.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)

        x = (canvas_width - new_width) // 2
        y = (canvas_height - new_height) // 2
        self.canvas.create_image(x, y, anchor=tk.NW, image=img_tk)
        self.canvas.image = img_tk
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        for line in self.highlight_lines:
            self.canvas.delete(line)
        self.highlight_lines.clear()

    def start_reading(self):
        if self.pdf_document and not self.is_reading:
            self.is_reading = True
            self.paused = False
            self.stop_reading = False
            self.play_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            threading.Thread(target=self.read_text).start()

    def read_text(self):
        while self.current_page < self.pages_count and not self.stop_reading:
            if not self.paused:
                page = self.pdf_document.load_page(self.current_page)
                self.text_positions = page.get_text("dict")["blocks"]

                for block in self.text_positions:
                    if self.stop_reading or self.paused:
                        break
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            bbox = span["bbox"]
                            self.highlight_word(bbox)
                            self.player.say(span["text"])
                            self.player.runAndWait()

                if not self.stop_reading and not self.paused:
                    self.current_page += 1
                    if self.current_page < self.pages_count:
                        self.display_page()
                        self.update_page_label()
        self.is_reading = False
        self.play_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.resume_button.config(state=tk.DISABLED)

    def pause_reading(self):
        if self.is_reading:
            self.paused = True
            self.play_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.NORMAL)

    def resume_reading(self):
        if self.paused:
            self.paused = False
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            threading.Thread(target=self.read_text).start()

    def highlight_word(self, bbox):
        x0, y0, x1, y1 = bbox
        x0 *= self.canvas.winfo_width() / self.pdf_document[self.current_page].rect.width
        y0 *= self.canvas.winfo_height() / self.pdf_document[self.current_page].rect.height
        x1 *= self.canvas.winfo_width() / self.pdf_document[self.current_page].rect.width
        y1 *= self.canvas.winfo_height() / self.pdf_document[self.current_page].rect.height

        line_y = (y0 + y1) / 2

        line = self.canvas.create_line(x0, line_y, x1, line_y, fill="red", width=1)
        self.highlight_lines.append(line)

    def play_page(self):
        self.pause_reading()
        try:
            page_number = int(self.page_entry.get()) - 1
            if 0 <= page_number < self.pages_count:
                self.current_page = page_number
                self.display_page()
                self.update_page_label()
                self.stop_reading = True
                self.is_reading = False
                threading.Thread(target=self.start_reading).start()
        except ValueError:
            pass

    def goto_page(self):
        self.pause_reading()
        try:
            page_number = int(self.page_entry.get()) - 1
            if 0 <= page_number < self.pages_count:
                self.current_page = page_number
                self.display_page()
                self.update_page_label()
                self.prev_page_button.config(state=tk.DISABLED if self.current_page == 0 else tk.NORMAL)
                self.next_page_button.config(state=tk.DISABLED if self.current_page == self.pages_count - 1 else tk.NORMAL)
                self.stop_reading = False
                threading.Thread(target=self.read_text).start()
        except ValueError:
            pass

    def next_page(self):
        if self.current_page < self.pages_count - 1:
            self.current_page += 1
            self.display_page()
            self.update_page_label()
            self.prev_page_button.config(state=tk.NORMAL)
            self.next_page_button.config(state=tk.DISABLED if self.current_page == self.pages_count - 1 else tk.NORMAL)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()
            self.update_page_label()
            self.prev_page_button.config(state=tk.DISABLED if self.current_page == 0 else tk.NORMAL)
            self.next_page_button.config(state=tk.NORMAL)

    def update_page_label(self):
        self.page_label.config(text=f"Page: {self.current_page + 1} / {self.pages_count}")

    def save_reading_position(self):
        if self.pdf_document:
            position = {
                "file": self.pdf_document.name,
                "current_page": self.current_page,
            }
            with open(self.config_file, "w") as f:
                json.dump(position, f)

    def load_reading_position(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                position = json.load(f)
                if position["file"] == self.pdf_document.name:
                    self.current_page = position["current_page"]

    def on_close(self):
        self.save_reading_position()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFReaderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
