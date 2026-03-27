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

# Waveshare Library Path
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 14  # Smaller font = more terminal space

class EInkBash:
    def __init__(self):
        self.epd = epd7in5_V2.EPD()
        self.epd.init_fast()
        
        # Setup Font and Grid
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        # Measure character size
        bbox = self.font.getbbox("M")
        self.cw, self.ch = bbox[2], bbox[3] + 2 
        
        self.cols = self.epd.width // self.cw
        self.rows = self.epd.height // self.ch
        
        # Terminal Emulator (Logic handler)
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self.screen)
        
        # Spawn the real Bash process
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # Child process
            os.environ["TERM"] = "linux"
            os.execvp("bash", ["bash"])

    def refresh_display(self):
        """Renders the pyte screen buffer to E-Ink."""
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)
        
        # Get the character grid from the terminal emulator
        for y, line in enumerate(self.screen.display):
            draw.text((0, y * self.ch), line, font=self.font, fill=0)
            
        self.epd.display(self.epd.getbuffer(img))

    def run(self):
        print(f"🖥️ Bash Terminal Active ({self.cols}x{self.rows})")
        print("Press Ctrl+C to exit.")
        
        # Set the parent terminal to raw mode to pass keys through
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin)
        
        try:
            while True:
                # Wait for either Bash output or User input
                r, w, e = select.select([self.fd, sys.stdin], [], [])
                
                if self.fd in r:
                    # Bash sent data
                    output = os.read(self.fd, 1024)
                    if not output:
                        break
                    self.stream.feed(output.decode('utf-8', 'ignore'))
                    self.refresh_display()
                    
                if sys.stdin in r:
                    # User typed a key
                    input_key = os.read(sys.stdin.fileno(), 1)
                    os.write(self.fd, input_key)
                    
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

if __name__ == "__main__":
    term = EInkBash()
    term.run()
