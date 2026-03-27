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
import time
from PIL import Image, ImageDraw, ImageFont

# Path setup for Waveshare
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2_old

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 14
BOTTOM_GAP = 10
RENDER_DELAY = 0.1 

class BarrierTerminal:
    def __init__(self):
        self.epd = epd7in5_V2_old.EPD()
        self.epd.init()
        self.epd.init_part()
        
        # IMPROVED: Load font and force strict character width
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        # Using a reliable method to get fixed width for Monospace
        self.cw = self.font.getlength(' ') # Use getlength for precise spacing
        if self.cw == 0: self.cw = 8 # Fallback
        
        # Height is font size + some padding
        self.ch = FONT_SIZE + 4
        
        self.cols = int(self.epd.width // self.cw)
        self.rows = int((self.epd.height - BOTTOM_GAP) // self.ch)
        
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self.screen)
        self.canvas = Image.new('1', (self.epd.width, self.epd.height), 255)
        self.draw = ImageDraw.Draw(self.canvas)
        
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.environ["TERM"] = "linux"
            tty_size = struct.pack("HHHH", self.rows, self.cols, 0, 0)
            fcntl.ioctl(sys.stdout.fileno(), termios.TIOCSWINSZ, tty_size)
            os.execvp("bash", ["bash"])

    def refresh(self):
        """Draws terminal state with strict grid alignment."""
        # Clear canvas
        self.draw.rectangle((0, 0, self.epd.width, self.epd.height), fill=255)
        
        # Render text line by line
        for y, line in enumerate(self.screen.display):
            # IMPROVED: We render the full line including spaces to maintain grid
            self.draw.text((0, y * self.ch), line, font=self.font, fill=0)
        
        # Cursor logic: Draw a small bar under the current position
        cx, cy = self.screen.cursor.x, self.screen.cursor.y
        if 0 <= cy < self.rows:
            cursor_x = cx * self.cw
            cursor_y = (cy * self.ch) + (self.ch - 2)
            self.draw.rectangle([cursor_x, cursor_y, cursor_x + self.cw, cursor_y + 2], fill=0)

        self.epd.display_Partial(self.epd.getbuffer(self.canvas), 0, 0, self.epd.width, self.epd.height)

    def run(self):
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin)
        
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        last_update = time.time()
        needs_update = False
        prefix_pressed = False 
        
        try:
            while True:
                r, _, _ = select.select([self.fd, sys.stdin], [], [], 0.01)
                
                if self.fd in r:
                    try:
                        while True:
                            data = os.read(self.fd, 4096)
                            if not data: break
                            self.stream.feed(data.decode('utf-8', 'ignore'))
                            needs_update = True
                            last_update = time.time()
                    except (BlockingIOError, OSError):
                        pass
                
                if sys.stdin in r:
                    key = os.read(sys.stdin.fileno(), 1)
                    
                    if key == b'\x02':  # Ctrl+B
                        prefix_pressed = True
                        continue 
                    
                    if prefix_pressed:
                        if key == b'd':
                            break 
                        else:
                            os.write(self.fd, b'\x02')
                            os.write(self.fd, key)
                            prefix_pressed = False
                    else:
                        os.write(self.fd, key)

                if needs_update and (time.time() - last_update) > RENDER_DELAY:
                    self.refresh()
                    needs_update = False
                    
        finally:
            # IMPORTANT: Completely shut down EPD to free SPI bus for other scripts
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print("\r\nReleasing E-ink Display...")
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep() # This puts the display in deep sleep and frees the bus
            print("[Detached]")

if __name__ == "__main__":
    BarrierTerminal().run()
