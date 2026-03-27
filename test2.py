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
MARGIN = 30 # Increased margin
FOOTER_RESERVE = 60 # Space at bottom to ensure visibility
SAVE_FILE = "reader_pos.json"

class NitroReader:
    def __init__(self, book_path):
        self.epd = epd7in5_V2.EPD()
        self.book_path = book_path
        
        print("⚡ Waking screen (Fast Mode)...")
        self.epd.init_fast() 
        
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 16)
        
        self.page_buffers = [] 
        self.page_text_map = [] # To store plain text per page for searching
        self.current_idx = 0
        
        self._load_and_preprocess()

    def _load_and_preprocess(self):
        print("📖 Indexing... (this happens once in RAM)")
        with open(self.book_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Calculate layout with visibility safety
        line_height = self.font.getbbox("Ay")[3] + 8
        # Ensure we leave enough room at the bottom for the hardware/footer
        usable_height = self.epd.height - (MARGIN * 2) - FOOTER_RESERVE
        lines_per_page = usable_height // line_height
        
        all_wrapped_lines = []
        canvas = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(canvas)
        
        for line in lines:
            words = line.split()
            if not words: 
                all_wrapped_lines.append("")
                continue
            curr_line = ""
            for word in words:
                test = curr_line + (" " if curr_line else "") + word
                if draw.textbbox((0,0), test, font=self.font)[2] < (self.epd.width - MARGIN*2):
                    curr_line = test
                else:
                    all_wrapped_lines.append(curr_line)
                    curr_line = word
            all_wrapped_lines.append(curr_line)

        total_pages = (len(all_wrapped_lines) + lines_per_page - 1) // lines_per_page
        for p in range(total_pages):
            img = Image.new("1", (self.epd.width, self.epd.height), 255)
            d = ImageDraw.Draw(img)
            
            page_lines = all_wrapped_lines[p*lines_per_page : (p+1)*lines_per_page]
            # Save raw text for search
            self.page_text_map.append(" ".join(page_lines).lower())
            
            for i, text_line in enumerate(page_lines):
                d.text((MARGIN, MARGIN + i*line_height), text_line, font=self.font, fill=0)
            
            footer = f"Page {p+1}/{total_pages}"
            # Centered footer shifted slightly UP to ensure visibility
            footer_w = d.textbbox((0,0), footer, font=self.footer_font)[2]
            d.text(((self.epd.width - footer_w)//2, self.epd.height - 45), footer, font=self.footer_font, fill=0)
            
            self.page_buffers.append(self.epd.getbuffer(img))
        
        if os.path.exists(SAVE_FILE):
            try:
                self.current_idx = json.load(open(SAVE_FILE)).get(self.book_path, 0)
            except: self.current_idx = 0

    def jump_to_page(self, page_num):
        idx = page_num - 1
        if 0 <= idx < len(self.page_buffers):
            self.current_idx = idx
            self.update_screen()
        else:
            print(f"❌ Invalid page. Range: 1-{len(self.page_buffers)}")

    def search(self, query):
        query = query.lower()
        print(f"🔍 Searching for '{query}'...")
        # Start search from the page AFTER current page
        for i in range(self.current_idx + 1, len(self.page_text_map)):
            if query in self.page_text_map[i]:
                print(f"✅ Found on page {i+1}")
                self.current_idx = i
                self.update_screen()
                return
        print("❌ Not found in the rest of the book.")

    def update_screen(self):
        self.epd.display(self.page_buffers[self.current_idx])
        self._save()

    def _save(self):
        json.dump({self.book_path: self.current_idx}, open(SAVE_FILE, 'w'))

def get_input_line(prompt):
    """Temporary switch back to normal terminal mode for typing."""
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

    reader = NitroReader(sys.argv[1])
    reader.update_screen()

    print("\n[D] Next  [A] Prev  [G] Go to Page  [/] Search  [Q] Quit")
    
    try:
        while True:
            k = get_key().lower()
            if k == 'q': break
            elif k == 'd': 
                if reader.current_idx < len(reader.page_buffers) - 1:
                    reader.current_idx += 1
                    reader.update_screen()
            elif k == 'a': 
                if reader.current_idx > 0:
                    reader.current_idx -= 1
                    reader.update_screen()
            elif k == 'g':
                val = get_input_line("🔢 Enter page number: ")
                if val.isdigit():
                    reader.jump_to_page(int(val))
            elif k == '/':
                query = get_input_line("🔍 Search for: ")
                if query:
                    reader.search(query)
    finally:
        reader.epd.init()
        reader.epd.Clear()
        reader.epd.sleep()
