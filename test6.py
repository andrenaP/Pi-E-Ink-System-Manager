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

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE = 20
MARGIN_X = 2
MARGIN_Y = 2
FOOTER_HEIGHT = 1  # Tightened for more text space
STATE_FILE = "reader_state.json"

class AdvancedReader:
    def __init__(self, book_path):
        self.book_path = book_path
        self.file_size = os.path.getsize(book_path)
        
        self.epd = epd7in5_V2.EPD()
        self.epd.init_fast() 
        
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 16)
        
        self.current_offset = 0
        self.history = [0]
        self._load_state()
        if self.current_offset == 0: self._skip_bom()

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    self.current_offset = json.load(f).get(self.book_path, 0)
            except: self.current_offset = 0

    def _save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump({self.book_path: self.current_offset}, f)

    def _skip_bom(self):
        with open(self.book_path, 'rb') as f:
            if f.read(3) == b'\xef\xbb\xbf': self.current_offset = 3

    def get_page_content(self, start_ptr):
        """Random access read and wrap."""
        with open(self.book_path, 'rb') as f:
            f.seek(start_ptr)
            blob = f.read(6144) # 6KB is plenty for one page
            text = blob.decode('utf-8', errors='ignore')

        lines = []
        max_w = self.epd.width - (MARGIN_X * 2)
        max_y = self.epd.height - FOOTER_HEIGHT - 10 
        line_height = self.font.getbbox("Ay")[3] + 8
        curr_y = MARGIN_Y
        
        paragraphs = text.split('\n')
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
            curr_y += line_height + 4 # Smaller paragraph gap

        # Calculate consumed bytes for the next jump
        displayed_text = "\n".join(lines)
        actual_bytes = len(displayed_text.encode('utf-8'))
        return lines, actual_bytes

    def render(self):
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)
        
        lines, consumed = self.get_page_content(self.current_offset)
        self.next_offset = self.current_offset + consumed
        
        line_height = self.font.getbbox("Ay")[3] + 8
        for i, l in enumerate(lines):
            draw.text((MARGIN_X, MARGIN_Y + i*line_height), l, font=self.font, fill=0)
            
        # Percentage Footer
        prog = (self.current_offset / self.file_size) * 100
        footer = f"{prog:.1f}% | Offset: {self.current_offset}"
        draw.text((MARGIN_X, self.epd.height - 30), footer, font=self.footer_font, fill=0)
        
        self.epd.display(self.epd.getbuffer(img))
        self._save_state()

    def search(self, query):
        """Search forward from current position."""
        print(f"\n🔍 Searching for: {query}")
        with open(self.book_path, 'rb') as f:
            f.seek(self.current_offset + 1)
            remaining = f.read().decode('utf-8', errors='ignore')
            idx = remaining.lower().find(query.lower())
            if idx != -1:
                self.history.append(self.current_offset)
                # Find the index in bytes, not characters
                found_text_segment = remaining[:idx]
                self.current_offset += len(found_text_segment.encode('utf-8'))
                self.render()
            else:
                print("❌ Not found.")

    def jump_to_percent(self, pct):
        target = int((pct / 100) * self.file_size)
        self.history.append(self.current_offset)
        self.current_offset = target
        self.render()

# --- Interaction Logic ---
def get_input(prompt):
    """Switch terminal modes to allow typing strings."""
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
        print("Usage: python3 reader.py mybook.txt")
        sys.exit()

    reader = AdvancedReader(sys.argv[1])
    reader.render()

    print("\nControls: [D] Next  [A] Back  [/] Search  [J] Jump %  [Q] Quit")
    
    try:
        while True:
            k = get_key().lower()
            if k == 'q': break
            elif k == 'd':
                if reader.next_offset < reader.file_size:
                    reader.history.append(reader.current_offset)
                    reader.current_offset = reader.next_offset
                    reader.render()
            elif k == 'a':
                if len(reader.history) > 1:
                    reader.current_offset = reader.history.pop()
                    reader.render()
            elif k == '/':
                q = get_input("Search: ")
                if q: reader.search(q)
            elif k == 'j':
                p = get_input("Jump to % (0-100): ")
                try: reader.jump_to_percent(float(p))
                except: print("Invalid number.")
    finally:
        reader.epd.init()
        reader.epd.Clear()
        reader.epd.sleep()
