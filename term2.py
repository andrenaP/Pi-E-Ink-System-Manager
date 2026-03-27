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
# Use a crisp monospace font
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 16  # Smaller font = better speed (less pixels to render)

class NitroTerminal:
    def __init__(self):
        self.epd = epd7in5_V2.EPD()
        print("⚡ Initializing High-Speed Mode...")
        
        # init_fast() is the key for the V2 board
        self.epd.init_fast()
        
        # Setup Font and Grid
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        # Measure character metrics
        bbox = self.font.getbbox("M")
        self.cw = bbox[2] - bbox[0]
        self.ch = bbox[3] - bbox[1] + 2 # Add leading
        
        self.cols = self.epd.width // self.cw
        self.rows = self.epd.height // self.ch
        
        # Virtual Terminal Logic
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self.screen)
        
        # Spawn Bash in a Pseudo-Terminal
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # Child process
            os.environ["TERM"] = "linux"
            os.environ["COLUMNS"] = str(self.cols)
            os.environ["LINES"] = str(self.rows)
            os.execvp("bash", ["bash"])

    def update_screen(self):
        """Renders the buffer and uses partial display logic."""
        # Create 1-bit canvas
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)
        
        # Render Pyte buffer
        for y, line in enumerate(self.screen.display):
            draw.text((0, y * self.ch), line, font=self.font, fill=0)
            
        # Draw the cursor (optional, for speed you can omit)
        cx, cy = self.screen.cursor.x, self.screen.cursor.y
        draw.rectangle([cx*self.cw, cy*self.ch, (cx+1)*self.cw, (cy+1)*self.ch], fill=0)

        # Waveshare 7.5 V2 Partial Logic:
        # We don't call init() again. We just push the buffer.
        # Note: If your specific lib doesn't have display_Partial, 
        # display() inside init_fast() is the closest equivalent.
        self.epd.display(self.epd.getbuffer(img))

    def run(self):
        print(f"📟 Terminal Ready ({self.cols}x{self.rows})")
        
        # Save old terminal settings to restore later
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin)
        
        try:
            while True:
                # Wait for bash output or user keypress
                r, w, e = select.select([self.fd, sys.stdin], [], [], 0.01)
                
                if self.fd in r:
                    output = os.read(self.fd, 1024)
                    if not output: break
                    self.stream.feed(output.decode('utf-8', 'ignore'))
                    self.update_screen()
                    
                if sys.stdin in r:
                    key = os.read(sys.stdin.fileno(), 1)
                    os.write(self.fd, key)
                    # For immediate feedback on keypress, you can update here too
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

if __name__ == "__main__":
    NitroTerminal().run()
