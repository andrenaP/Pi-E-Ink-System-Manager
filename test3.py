#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import json
import termios
import tty
from PIL import Image, ImageDraw, ImageFont

# Setup Waveshare Paths
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2

# Configuration
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE = 22
MARGIN = 30
FOOTER_RESERVE = 60 
SAVE_FILE = "reader_pos.json"

class LazyReader:
    def __init__(self, book_path):
        self.epd = epd7in5_V2.EPD()
        self.book_path = book_path
        
        print("⚡ Waking screen...")
        self.epd.init_fast() 
        
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 16)
        
        # We store LINES of text, not BUFFERS. 
        # This saves 99% of your RAM.
        self.pages = [] 
        self.current_idx = 0
        
        self._paginate_lazy()
        self._load_state()

    def _paginate_lazy(self):
        """Quickly calculates page breaks without rendering images."""
        print("📖 Indexing book structure...")
        with open(self.book_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Measure once
        line_height = self.font.getbbox("Ay")[3] + 8
        usable_height = self.epd.height - (MARGIN * 2) - FOOTER_RESERVE
        lines_per_page = usable_height // line_height
        
        all_wrapped_lines = []
        # We use a 1x1 image just to measure text width
        test_draw = ImageDraw.Draw(Image.new("1", (1, 1)))
        max_w = self.epd.width - (MARGIN * 2)

        # FAST WRAPPING: This is the only bottleneck now
        for paragraph in content.splitlines():
            words = paragraph.split()
            if not words:
                all_wrapped_lines.append("")
                continue
            curr_line = ""
            for word in words:
                test = curr_line + (" " if curr_line else "") + word
                # measure width
                w = test_draw.textbbox((0,0), test, font=self.font)[2]
                if w < max_w:
                    curr_line = test
                else:
                    all_wrapped_lines.append(curr_line)
                    curr_line = word
            all_wrapped_lines.append(curr_line)

        # Chunk lines into pages (list of lists of strings)
        self.pages = [all_wrapped_lines[i : i + lines_per_page] for i in range(0, len(all_wrapped_lines), lines_per_page)]
        print(f"✅ Indexed {len(self.pages)} pages.")

    def render_current_page(self):
        """Renders ONLY the current page into a buffer."""
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        d = ImageDraw.Draw(img)
        
        line_height = self.font.getbbox("Ay")[3] + 8
        page_lines = self.pages[self.current_idx]
        
        for i, text_line in enumerate(page_lines):
            d.text((MARGIN, MARGIN + i*line_height), text_line, font=self.font, fill=0)
        
        footer = f"Page {self.current_idx + 1} / {len(self.pages)}"
        footer_w = d.textbbox((0,0), footer, font=self.footer_font)[2]
        d.text(((self.epd.width - footer_w)//2, self.epd.height - 45), footer, font=self.footer_font, fill=0)
        
        return self.epd.getbuffer(img)

    def update_screen(self):
        buf = self.render_current_page()
        self.epd.display(buf)
        self._save()

    def search(self, query):
        query = query.lower()
        print(f"🔍 Searching for '{query}'...")
        for i in range(self.current_idx + 1, len(self.pages)):
            # Join lines of the page and check
            if query in " ".join(self.pages[i]).lower():
                print(f"✅ Found on page {i+1}")
                self.current_idx = i
                self.update_screen()
                return
        print("❌ Not found.")

    def _save(self):
        json.dump({self.book_path: self.current_idx}, open(SAVE_FILE, 'w'))

    def _load_state(self):
        if os.path.exists(SAVE_FILE):
            try:
                self.current_idx = json.load(open(SAVE_FILE)).get(self.book_path, 0)
                if self.current_idx >= len(self.pages): self.current_idx = 0
            except: pass

# --- UI Functions ---
def get_input_line(prompt):
    print("\n" + prompt, end="", flush=True)
    return sys.stdin.readline().strip()

def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 reader.py book.txt")
        sys.exit()

    reader = LazyReader(sys.argv[1])
    reader.update_screen()

    print("\n[D] Next  [A] Prev  [G] Go to Page  [/] Search  [Q] Quit")
    
    try:
        while True:
            k = get_key().lower()
            if k == 'q': break
            elif k == 'd': 
                if reader.current_idx < len(reader.pages) - 1:
                    reader.current_idx += 1
                    reader.update_screen()
            elif k == 'a': 
                if reader.current_idx > 0:
                    reader.current_idx -= 1
                    reader.update_screen()
            elif k == 'g':
                val = get_input_line("🔢 Enter page number: ")
                if val.isdigit():
                    reader.current_idx = int(val) - 1
                    reader.update_screen()
            elif k == '/':
                query = get_input_line("🔍 Search for: ")
                if query: reader.search(query)
    finally:
        reader.epd.init()
        reader.epd.Clear()
        reader.epd.sleep()
