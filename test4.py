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
STATE_FILE = "reader_state.json"

class InstantReader:
    def __init__(self, book_path):
        self.epd = epd7in5_V2.EPD()
        self.book_path = book_path
        self.file_size = os.path.getsize(book_path)
        
        print("⚡ Waking screen...")
        self.epd.init_fast() 
        
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 16)
        
        # Navigation State
        self.current_offset = 0  # Byte position in file
        self.history = []        # Stack of previous offsets for 'Back' button
        
        self._load_state()
        
    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                state = json.load(open(STATE_FILE))
                self.current_offset = state.get(self.book_path, 0)
            except: pass

    def _save_state(self):
        json.dump({self.book_path: self.current_offset}, open(STATE_FILE, 'w'))

    def render_and_display(self):
        """Reads from current offset and wraps only enough for one page."""
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)
        
        # 1. Read a chunk from the file
        with open(self.book_path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(self.current_offset)
            # Read 4KB - plenty for one 800x480 page
            raw_text = f.read(4096) 

        # 2. Wrap text on the fly
        line_height = self.font.getbbox("Ay")[3] + 8
        max_y = self.epd.height - MARGIN - FOOTER_RESERVE
        max_w = self.epd.width - (MARGIN * 2)
        
        y = MARGIN
        consumed_chars = 0
        lines = raw_text.splitlines()
        
        # Tracking for next page offset
        finished_page = False
        
        for line in lines:
            words = line.split()
            if not words: # Paragraph break
                y += line_height
                consumed_chars += 1 # for the newline
                if y + line_height > max_y: break
                continue
                
            curr_line_str = ""
            for word in words:
                test_str = curr_line_str + (" " if curr_line_str else "") + word
                w = draw.textbbox((0,0), test_str, font=self.font)[2]
                
                if w < max_w:
                    curr_line_str = test_str
                else:
                    # Draw current line and move to next
                    draw.text((MARGIN, y), curr_line_str, font=self.font, fill=0)
                    y += line_height
                    curr_line_str = word
                    if y + line_height > max_y:
                        finished_page = True
                        break
            
            if finished_page: break
            
            # Draw the last piece of the paragraph
            draw.text((MARGIN, y), curr_line_str, font=self.font, fill=0)
            y += line_height
            consumed_chars += len(line) + 1 # +1 for newline
            if y + line_height > max_y: break

        # 3. Finalize Footer & Display
        progress = (self.current_offset / self.file_size) * 100
        footer = f"{progress:.1f}% through book"
        draw.text((self.epd.width//2 - 40, self.epd.height - 45), footer, font=self.footer_font, fill=0)
        
        self.epd.display(self.epd.getbuffer(img))
        
        # Important: We need to know where this page ended to find the NEXT offset
        # This is a bit tricky with UTF-8, but for a reader, estimating works:
        self.next_page_offset = self.current_offset + consumed_chars
        self._save_state()

    def go_next(self):
        self.history.append(self.current_offset)
        self.current_offset = self.next_page_offset
        self.render_and_display()

    def go_back(self):
        if self.history:
            self.current_offset = self.history.pop()
            self.render_and_display()

    def jump_to_percent(self, percent):
        target = int((percent / 100) * self.file_size)
        self.history.append(self.current_offset)
        self.current_offset = target
        self.render_and_display()

# --- Terminal UI ---
def get_input(prompt):
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

    reader = InstantReader(sys.argv[1])
    reader.render_and_display()

    print("\n[D] Next  [A] Back  [G] Jump %  [Q] Quit")
    try:
        while True:
            k = get_key().lower()
            if k == 'q': break
            elif k == 'd': reader.go_next()
            elif k == 'a': reader.go_back()
            elif k == 'g':
                p = get_input("🔢 Enter % to jump (0-100): ")
                if p.isdigit(): reader.jump_to_percent(int(p))
    finally:
        reader.epd.init()
        reader.epd.Clear()
        reader.epd.sleep()
