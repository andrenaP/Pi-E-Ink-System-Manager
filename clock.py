#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import time
import socket
import psutil
import select
import termios
import tty
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Configuration
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
TIME_SIZE = 90
STAT_SIZE = 24

class PrecisionDash:
    def __init__(self, epd):
        self.epd = epd  # Accept the screen from the menu!
        self.time_font = ImageFont.truetype(FONT_PATH, TIME_SIZE)
        self.stat_font = ImageFont.truetype(FONT_PATH, STAT_SIZE)

    def get_stats(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except: ip = "Disconnected"

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        temp = 0
        if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read()) / 1000

        return {
            "time": datetime.now().strftime("%H:%M"),
            "date": datetime.now().strftime("%a, %b %d"),
            "ip": f"IP: {ip}",
            "stats": f"CPU: {cpu}% | RAM: {ram}% | {temp:.1f}°C"
        }

    def update(self):
        data = self.get_stats()
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)

        tw = draw.textbbox((0,0), data["time"], font=self.time_font)[2]
        draw.text(((self.epd.width - tw)//2, 80), data["time"], font=self.time_font, fill=0)

        dw = draw.textbbox((0,0), data["date"], font=self.stat_font)[2]
        draw.text(((self.epd.width - dw)//2, 190), data["date"], font=self.stat_font, fill=0)

        sw = draw.textbbox((0,0), data["stats"], font=self.stat_font)[2]
        draw.text(((self.epd.width - sw)//2, 330), data["stats"], font=self.stat_font, fill=0)
        draw.text((30, self.epd.height - 50), data["ip"], font=self.stat_font, fill=0)

        self.epd.display(self.epd.getbuffer(img))

# --- STANDARD ENTRY POINT ---
def run_app(epd, *args):
    dash = PrecisionDash(epd)
    
    # Switch to raw terminal input so we can detect 'q' to exit
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin)
    
    try:
        while True:
            dash.update()
            
            # Wait for next minute, checking for 'q' every 0.1 seconds
            now = datetime.now()
            seconds_to_wait = 60 - now.second - (now.microsecond / 1000000.0)
            
            quit_app = False
            while seconds_to_wait > 0:
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    if sys.stdin.read(1).lower() == 'q':
                        quit_app = True
                        break
                seconds_to_wait -= 0.1
                
            if quit_app: break
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
