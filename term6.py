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
RENDER_DELAY = 0.05  # 50ms barrier to prevent "letter-by-letter" rendering

class BarrierTerminal:
    def __init__(self):
        self.epd = epd7in5_V2_old.EPD()
        self.epd.init()
        self.epd.init_part()
        
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        bbox = self.font.getbbox("M")
        self.cw, self.ch = (bbox[2] - bbox[0]), (bbox[3] - bbox[1] + 2)
        
        self.cols = self.epd.width // self.cw
        self.rows = (self.epd.height - BOTTOM_GAP) // self.ch
        
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
        """Draws current terminal state to screen."""
        self.draw.rectangle((0, 0, self.epd.width, self.epd.height), fill=255)
        for y, line in enumerate(self.screen.display):
            if line.strip():
                self.draw.text((0, y * self.ch), line, font=self.font, fill=0)
        
        # Cursor
        cx, cy = self.screen.cursor.x, self.screen.cursor.y
        if 0 <= cy < self.rows:
            self.draw.rectangle([cx*self.cw, cy*self.ch, (cx+1)*self.cw, (cy+1)*self.ch], fill=0)

        self.epd.display_Partial(self.epd.getbuffer(self.canvas), 0, 0, self.epd.width, self.epd.height)

    def run(self):
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin)
        # Set Bash FD to non-blocking
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        last_update = time.time()
        needs_update = False
        
        try:
            while True:
                # Use a very short timeout for select
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
                    os.write(self.fd, key)

                # --- THE BARRIER LOGIC ---
                # Only refresh if we need an update AND it's been 50ms since the last char arrived
                if needs_update and (time.time() - last_update) > RENDER_DELAY:
                    self.refresh()
                    needs_update = False
                    
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

if __name__ == "__main__":
    BarrierTerminal().run()
