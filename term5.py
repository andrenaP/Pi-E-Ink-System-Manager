#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import pty
import select
import termios
import tty
import pyte
import fcntl
import struct
import logging
from PIL import Image, ImageDraw, ImageFont

# Path setup for Waveshare
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2_old

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 14 
BOTTOM_GAP = 40  # Gap in pixels at the bottom

class NitroBash:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.epd = epd7in5_V2_old.EPD()
        
        # 1. Hardware Init
        self.epd.init()
        self.epd.init_part()
        
        # 2. Setup Font & Grid
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        bbox = self.font.getbbox("M")
        self.cw = bbox[2] - bbox[0]
        self.ch = bbox[3] - bbox[1] + 2
        
        self.cols = self.epd.width // self.cw
        # Create gap at the bottom by reducing row count
        self.rows = (self.epd.height - BOTTOM_GAP) // self.ch
        
        # 3. Terminal Emulator
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self.screen)
        
        # 4. Persistence Buffer
        self.canvas = Image.new('1', (self.epd.width, self.epd.height), 255)
        self.draw = ImageDraw.Draw(self.canvas)
        
        # 5. Spawn Bash with Window Size Signaling
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # Child process
            os.environ["TERM"] = "linux"
            # Crucial for btop/htop to see the screen size
            tty_size = struct.pack("HHHH", self.rows, self.cols, 0, 0)
            fcntl.ioctl(sys.stdout.fileno(), termios.TIOCSWINSZ, tty_size)
            os.execvp("bash", ["bash"])

    def refresh_screen(self):
        """Perform the fast partial update of current state only."""
        self.draw.rectangle((0, 0, self.epd.width, self.epd.height), fill=255)
        
        for y, line in enumerate(self.screen.display):
            if line.strip(): # Skip empty lines for speed
                self.draw.text((0, y * self.ch), line, font=self.font, fill=0)
            
        cx, cy = self.screen.cursor.x, self.screen.cursor.y
        if 0 <= cy < self.rows:
            self.draw.rectangle([cx*self.cw, cy*self.ch, (cx+1)*self.cw, (cy+1)*self.ch], fill=0)

        # Push to screen
        self.epd.display_Partial(self.epd.getbuffer(self.canvas), 0, 0, self.epd.width, self.epd.height)

    def run(self):
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin)
        
        try:
            while True:
                # Select with short timeout
                r, _, _ = select.select([self.fd, sys.stdin], [], [], 0.02)
                
                if self.fd in r:
                    # Read all available data from Bash to avoid rendering every single char
                    data = b""
                    while True:
                        try:
                            # Non-blocking read
                            chunk = os.read(self.fd, 4096)
                            if not chunk: break
                            data += chunk
                            # If we hit a small chunk, we've likely cleared the buffer
                            if len(chunk) < 4096: break 
                        except BlockingIOError:
                            break
                    
                    if data:
                        self.stream.feed(data.decode('utf-8', 'ignore'))
                        # Only refresh after we've processed the whole current "chunk"
                        self.refresh_screen()
                    
                if sys.stdin in r:
                    user_input = os.read(sys.stdin.fileno(), 1)
                    os.write(self.fd, user_input)
                    
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

if __name__ == "__main__":
    NitroBash().run()
