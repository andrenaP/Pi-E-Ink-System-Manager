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
FONT_SIZE = 24
MARGIN = 40
FOOTER_RESERVE = 60 
STATE_FILE = "reader_state.json"

class FinalReader:
    def __init__(self, book_path):
        self.book_path = book_path
        self.file_size = os.path.getsize(book_path)
        
        # 1. Start Hardware immediately
        self.epd = epd7in5_V2.EPD()
        self.epd.init_fast() 
        
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 16)
        
        # 2. Set Pointer (Priority: Saved State > Beginning of File)
        self.current_offset = 0
        self.history = [0]
        self._load_state()
        
        # 3. Handle UTF-8 BOM if it exists at offset 0
        if self.current_offset == 0:
            self._skip_bom()

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.current_offset = data.get(self.book_path, 0)
                    print(f"📖 Resuming from byte: {self.current_offset}")
            except:
                self.current_offset = 0

    def _skip_bom(self):
        """Skips the UTF-8 Byte Order Mark if present at the start of the file."""
        with open(self.book_path, 'rb') as f:
            chunk = f.read(3)
            if chunk == b'\xef\xbb\xbf':
                self.current_offset = 3

    def get_page_data(self, start_ptr):
        """Reads a safe chunk and wraps it to the screen."""
        with open(self.book_path, 'rb') as f:
            f.seek(start_ptr)
            # Read a larger buffer to account for long paragraphs
            blob = f.read(8192)
            # Safe decode: ignore fragments at the end of the buffer
            text = blob.decode('utf-8', errors='ignore')

        lines = []
        max_w = self.epd.width - (MARGIN * 2)
        max_y = self.epd.height - MARGIN - FOOTER_RESERVE
        
        # Measure line height
        line_height = self.font.getbbox("Ay")[3] + 10
        curr_y = MARGIN
        
        # Split by newlines but keep track of how much text we actually display
        paragraphs = text.split('\n')
        chars_displayed = 0
        
        temp_img = Image.new("1", (1, 1))
        draw = ImageDraw.Draw(temp_img)

        for p in paragraphs:
            words = p.split(' ')
            line = ""
            for word in words:
                test_line = line + (" " if line else "") + word
                w = draw.textbbox((0, 0), test_line, font=self.font)[2]
                
                if w <= max_w:
                    line = test_line
                else:
                    lines.append(line)
                    curr_y += line_height
                    line = word
                    if curr_y + line_height > max_y: break
            
            if curr_y + line_height > max_y: break
            
            lines.append(line)
            curr_y += line_height + 5 # Paragraph spacing
            chars_displayed += len(p) + 1 # +1 for the \n we split on

        # Convert the actually displayed text back to bytes to find the exact next offset
        displayed_text = "\n".join(lines)
        actual_bytes = len(displayed_text.encode('utf-8'))
        
        return lines, actual_bytes

    def display_page(self):
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)
        
        lines, consumed_bytes = self.get_page_data(self.current_offset)
        self.next_offset = self.current_offset + consumed_bytes
        
        # Render
        line_height = self.font.getbbox("Ay")[3] + 10
        for i, l in enumerate(lines):
            draw.text((MARGIN, MARGIN + i*line_height), l, font=self.font, fill=0)
            
        # Footer with percentage
        progress = (self.current_offset / self.file_size) * 100
        footer = f"{progress:.1f}% | Byte: {self.current_offset}"
        draw.text((MARGIN, self.epd.height - 40), footer, font=self.footer_font, fill=0)
        
        self.epd.display(self.epd.getbuffer(img))
        self._save_state()

    def _save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump({self.book_path: self.current_offset}, f)

    def next(self):
        if self.next_offset < self.file_size:
            self.history.append(self.current_offset)
            self.current_offset = self.next_offset
            self.display_page()

    def prev(self):
        if len(self.history) > 1:
            self.current_offset = self.history.pop()
            self.display_page()
        else:
            self.current_offset = 0
            self.display_page()

# --- Input Handling ---
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

    reader = FinalReader(sys.argv[1])
    reader.display_page()

    while True:
        k = get_key().lower()
        if k == 'q': break
        elif k == 'd': reader.next()
        elif k == 'a': reader.prev()
