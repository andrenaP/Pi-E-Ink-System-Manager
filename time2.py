#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import time
import socket
import psutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Setup Waveshare Paths
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2

# Configuration
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
TIME_SIZE = 90  # Large clock
STAT_SIZE = 24

class PrecisionDash:
    def __init__(self):
        self.epd = epd7in5_V2.EPD()
        print("⚡ Waking screen...")
        self.epd.init_fast() 
        
        self.time_font = ImageFont.truetype(FONT_PATH, TIME_SIZE)
        self.stat_font = ImageFont.truetype(FONT_PATH, STAT_SIZE)

    def get_stats(self):
        """Fetches system data."""
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
        """Renders and displays the info."""
        data = self.get_stats()
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)

        # Draw Big Time
        tw = draw.textbbox((0,0), data["time"], font=self.time_font)[2]
        draw.text(((self.epd.width - tw)//2, 80), data["time"], font=self.time_font, fill=0)

        # Draw Date
        dw = draw.textbbox((0,0), data["date"], font=self.stat_font)[2]
        draw.text(((self.epd.width - dw)//2, 190), data["date"], font=self.stat_font, fill=0)

        # Draw Stats Footer
        sw = draw.textbbox((0,0), data["stats"], font=self.stat_font)[2]
        draw.text(((self.epd.width - sw)//2, 330), data["stats"], font=self.stat_font, fill=0)
        draw.text((30, self.epd.height - 50), data["ip"], font=self.stat_font, fill=0)

        print(f"🔄 Minute sync refresh at: {datetime.now().strftime('%H:%M:%S')}")
        self.epd.display(self.epd.getbuffer(img))

    def run(self):
        while True:
            # 1. Update the screen at the start of the minute
            self.update()

            # 2. Calculate time until the EXACT start of the next minute
            now = datetime.now()
            # Seconds remaining + microseconds converted to seconds
            seconds_to_wait = 60 - now.second - (now.microsecond / 1000000.0)
            
            # 3. Sleep until the clock strikes :00
            # We add a tiny 0.1s buffer to ensure we don't trigger at :59.999
            time.sleep(max(0, seconds_to_wait + 0.1))

if __name__ == "__main__":
    dash = PrecisionDash()
    try:
        dash.run()
    except KeyboardInterrupt:
        dash.epd.init()
        dash.epd.Clear()
        dash.epd.sleep()
