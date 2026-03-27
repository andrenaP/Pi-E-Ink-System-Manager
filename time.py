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
TITLE_SIZE = 40
DATA_SIZE = 28

class SystemDash:
    def __init__(self):
        self.epd = epd7in5_V2.EPD()
        self.epd.init() # Full init for the first frame
        self.width = self.epd.width
        self.height = self.epd.height
        
        self.title_font = ImageFont.truetype(FONT_PATH, TITLE_SIZE)
        self.data_font = ImageFont.truetype(FONT_PATH, DATA_SIZE)

    def get_stats(self):
        """Gather system information."""
        # Get IP Address
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = "Disconnected"

        cpu_usage = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        temp = 0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read()) / 1000
        except: pass

        return {
            "time": datetime.now().strftime("%H:%M"),
            "date": datetime.now().strftime("%A, %b %d %Y"),
            "ip": f"IP: {ip}",
            "cpu": f"CPU: {cpu_usage}%",
            "ram": f"RAM: {ram.percent}%",
            "temp": f"Temp: {temp:.1f}°C"
        }

    def run(self):
        print("🚀 Starting Dashboard. Press Ctrl+C to stop.")
        
        # Initial Full Clear
        self.epd.Clear()
        
        while True:
            stats = self.get_stats()
            
            # Create Buffer
            img = Image.new("1", (self.width, self.height), 255)
            draw = ImageDraw.Draw(img)
            
            # Draw Time and Date (Center Top)
            draw.text((self.width//2 - 60, 40), stats["time"], font=self.title_font, fill=0)
            draw.text((self.width//2 - 140, 90), stats["date"], font=self.data_font, fill=0)
            
            # Draw Stats Box
            y_start = 180
            draw.rectangle((100, y_start - 20, self.width - 100, self.height - 100), outline=0)
            
            draw.text((150, y_start + 20), stats["ip"], font=self.data_font, fill=0)
            draw.text((150, y_start + 70), stats["cpu"], font=self.data_font, fill=0)
            draw.text((150, y_start + 120), stats["ram"], font=self.data_font, fill=0)
            draw.text((150, y_start + 170), stats["temp"], font=self.data_font, fill=0)

            # Use display() but note that 7.5" V2 supports partial updates 
            # via specific logic if you want even faster refreshes. 
            # For 1-minute intervals, a clean update is safest for screen health.
            self.epd.display(self.epd.getbuffer(img))
            
            # Sleep until the next minute starts
            time.sleep(60 - datetime.now().second)

if __name__ == "__main__":
    dash = SystemDash()
    try:
        dash.run()
    except KeyboardInterrupt:
        print("Cleaning up...")
        dash.epd.init()
        dash.epd.Clear()
        dash.epd.sleep()
