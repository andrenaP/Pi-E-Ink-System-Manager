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

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 14
BOTTOM_GAP = 10
RENDER_DELAY = 0.5

class BarrierTerminal:
    def __init__(self, epd):
        self.epd = epd # Accept screen from menu
        
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.cw = self.font.getlength(' ') 
        if self.cw == 0: self.cw = 8 
        
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
        self.draw.rectangle((0, 0, self.epd.width, self.epd.height), fill=255)
        for y, line in enumerate(self.screen.display):
            self.draw.text((0, y * self.ch), line, font=self.font, fill=0)
        
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
                    except (BlockingIOError, OSError): pass
                
                if sys.stdin in r:
                    key = os.read(sys.stdin.fileno(), 1)
                    if key == b'\x02':  # Ctrl+B
                        prefix_pressed = True
                        continue 
                    
                    if prefix_pressed:
                        if key == b'd': break 
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
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

# --- STANDARD ENTRY POINT ---
def run_app(epd, *args):
    #epd.init()
    #epd.Clear()
    #epd.init_part()
    
    term = BarrierTerminal(epd)
    term.run()
