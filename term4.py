#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import pty
import select
import termios
import tty
import pyte
import logging
from PIL import Image, ImageDraw, ImageFont

# Path setup for Waveshare
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2_old # Using the version from your example

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 18 

class NitroBash:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.epd = epd7in5_V2_old.EPD()
        
        # 1. Initial Hardware Setup
        logging.info("Init and Clear")
        self.epd.init()
        self.epd.Clear()
        
        # 2. Enter Partial Mode (Crucial for speed)
        logging.info("Entering Partial Update Mode")
        self.epd.init_part()
        
        # 3. Setup Terminal Emulator
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        # Measure char size (standard for monospace)
        char_bbox = self.font.getbbox("M")
        self.cw = char_bbox[2] - char_bbox[0]
        self.ch = char_bbox[3] - char_bbox[1] + 2
        
        self.cols = self.epd.width // self.cw
        self.rows = self.epd.height // self.ch
        
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self.screen)
        
        # 4. Persistence Image Buffer
        self.canvas = Image.new('1', (self.epd.width, self.epd.height), 255)
        self.draw = ImageDraw.Draw(self.canvas)
        
        # 5. Spawn Bash
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # Child
            os.environ["TERM"] = "linux"
            os.environ["COLUMNS"] = str(self.cols)
            os.environ["LINES"] = str(self.rows)
            os.execvp("bash", ["bash"])

    def refresh_screen(self):
        """Perform the fast partial update."""
        # Clear the internal canvas
        self.draw.rectangle((0, 0, self.epd.width, self.epd.height), fill=255)
        
        # Render terminal rows
        for y, line in enumerate(self.screen.display):
            self.draw.text((0, y * self.ch), line, font=self.font, fill=0)
            
        # Optional: Draw cursor
        cx, cy = self.screen.cursor.x, self.screen.cursor.y
        self.draw.rectangle([cx*self.cw, cy*self.ch, (cx+1)*self.cw, (cy+1)*self.ch], fill=0)

        # FAST PARTIAL UPDATE (The logic from your example)
        self.epd.display_Partial(self.epd.getbuffer(self.canvas), 0, 0, self.epd.width, self.epd.height)

    def run(self):
        # Set host terminal to raw to catch every key
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin)
        
        try:
            while True:
                # Select loop to monitor Bash and Keyboard
                r, _, _ = select.select([self.fd, sys.stdin], [], [], 0.02)
                
                if self.fd in r:
                    data = os.read(self.fd, 1024)
                    if not data: break
                    self.stream.feed(data.decode('utf-8', 'ignore'))
                    self.refresh_screen()
                    
                if sys.stdin in r:
                    user_input = os.read(sys.stdin.fileno(), 1)
                    os.write(self.fd, user_input)
                    
        finally:
            # Restore terminal and clean screen
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            logging.info("Exiting and Cleaning...")
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

if __name__ == "__main__":
    NitroBash().run()
