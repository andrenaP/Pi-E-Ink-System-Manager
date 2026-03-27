#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import json
import logging
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
MARGIN = 20
SAVE_FILE = "reader_pos.json"

class NitroReader:
    def __init__(self, book_path):
        self.epd = epd7in5_V2.EPD()
        self.book_path = book_path
        
        # 1. Initialize Screen ONCE with Fast Mode
        print("⚡ Waking screen (Fast Mode)...")
        self.epd.init_fast() 
        
        # 2. Pre-load Font
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 14)
        
        # 3. Pagination Engine
        self.page_buffers = [] # This stores ready-to-send Waveshare buffers
        self.current_idx = 0
        self._load_and_preprocess()

    def _load_and_preprocess(self):
        """Convert the entire book into Waveshare-ready buffers in RAM."""
        print("📖 Indexing and Rendering pages to RAM...")
        with open(self.book_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Calculate layout
        line_height = self.font.getbbox("Ay")[3] + 8
        lines_per_page = (self.epd.height - (MARGIN * 2) - 30) // line_height
        
        # Wrap text
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

        # Create buffers
        total_pages = (len(all_wrapped_lines) + lines_per_page - 1) // lines_per_page
        for p in range(total_pages):
            img = Image.new("1", (self.epd.width, self.epd.height), 255)
            d = ImageDraw.Draw(img)
            
            # Draw Text
            page_lines = all_wrapped_lines[p*lines_per_page : (p+1)*lines_per_page]
            for i, text_line in enumerate(page_lines):
                d.text((MARGIN, MARGIN + i*line_height), text_line, font=self.font, fill=0)
            
            # Draw Footer
            footer = f"Page {p+1}/{total_pages}"
            d.text((self.epd.width//2, self.epd.height-25), footer, font=self.footer_font, fill=0)
            
            # CRITICAL: Store the raw buffer, not the Image object
            self.page_buffers.append(self.epd.getbuffer(img))
        
        # Load position
        if os.path.exists(SAVE_FILE):
            self.current_idx = json.load(open(SAVE_FILE)).get(self.book_path, 0)

    def turn_page(self, delta):
        new_idx = self.current_idx + delta
        if 0 <= new_idx < len(self.page_buffers):
            self.current_idx = new_idx
            # FASTEST POSSIBLE ACTION: Send pre-computed buffer
            self.epd.display(self.page_buffers[self.current_idx])
            self._save()

    def _save(self):
        json.dump({self.book_path: self.current_idx}, open(SAVE_FILE, 'w'))

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
    reader.turn_page(0) # Show current page

    print("\n[D] Next  [A] Prev  [Q] Quit")
    try:
        while True:
            k = get_key().lower()
            if k == 'q': break
            if k == 'd': reader.turn_page(1)
            if k == 'a': reader.turn_page(-1)
    finally:
        # Only clear/sleep when totally done
        reader.epd.init() # Full re-init to ensure a clean final clear
        reader.epd.Clear()
        reader.epd.sleep()
