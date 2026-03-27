#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import pty
import select
import termios
import tty
import pyte
from PIL import Image, ImageDraw, ImageFont

# Waveshare Pathing
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2

# --- Config ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 14 # Small font = less pixel data to process

class InstantTerminal:
    def __init__(self):
        self.epd = epd7in5_V2.EPD()
        
        # ONCE AT START: Initial hardware wake-up
        print("⚡ Hardware Init...")
        self.epd.init_fast() 
        
        self.width = self.epd.width
        self.height = self.epd.height
        
        # Monospace Font Metrics
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        bbox = self.font.getbbox("M")
        self.cw = bbox[2] - bbox[0]
        self.ch = bbox[3] - bbox[1] + 2
        
        self.cols = self.width // self.cw
        self.rows = self.height // self.ch
        
        # Terminal Engine
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self.screen)
        
        # Spawn Shell
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.environ["TERM"] = "linux"
            os.execvp("bash", ["bash"])

    def refresh(self):
        """Ultra-fast rendering loop."""
        # Create a 1-bit '1' image directly (Black and White only)
        img = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)
        
        # Draw the terminal buffer
        for y, line in enumerate(self.screen.display):
            if line.strip(): # Only draw non-empty lines to save CPU cycles
                draw.text((0, y * self.ch), line, font=self.font, fill=0)
        
        # Direct display call - NO RE-INIT
        # This sends the data directly to the SRAM of the E-Ink controller
        self.epd.display(self.epd.getbuffer(img))

    def run(self):
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin)
        
        try:
            while True:
                # Watch for data from Bash or User
                r, _, _ = select.select([self.fd, sys.stdin], [], [], 0.05)
                
                dirty = False
                if self.fd in r:
                    data = os.read(self.fd, 1024)
                    if data:
                        self.stream.feed(data.decode('utf-8', 'ignore'))
                        dirty = True
                
                if sys.stdin in r:
                    key = os.read(sys.stdin.fileno(), 1)
                    os.write(self.fd, key)
                    # We don't refresh here; we wait for Bash to echo the char back
                
                if dirty:
                    self.refresh()
                    
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            # Final cleanup only on exit
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

if __name__ == "__main__":
    InstantTerminal().run()
