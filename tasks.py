import os
import sys
import time
import socket
import psutil
import subprocess  # Added for CLI interaction
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Setup Waveshare Paths
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2

# Configuration
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
TIME_SIZE = 90
STAT_SIZE = 20 # Sized down slightly for more room
TASK_SIZE = 22

class PrecisionDash:
    def __init__(self):
        self.epd = epd7in5_V2.EPD()
        print("⚡ Waking screen...")
        self.epd.init_fast() 
        
        self.time_font = ImageFont.truetype(FONT_PATH, TIME_SIZE)
        self.stat_font = ImageFont.truetype(FONT_PATH, STAT_SIZE)
        self.task_font = ImageFont.truetype(FONT_PATH, TASK_SIZE)
        
        self.cached_tasks = []
        self.last_task_update = -1 # Force update on first run

    def get_tasks(self):
        """Fetches top 5 pending tasks from Taskwarrior."""
        try:
            # 'rc.verbose=nothing' removes the header/footer text from the output
            # 'limit:5' keeps the list short for the screen
            cmd = ["task", "rc.verbose=nothing", "rc.report.next.columns=description", "limit:5", "next"]
            result = subprocess.check_output(cmd).decode("utf-8")
            tasks = [line.strip() for line in result.split('\n') if line.strip()]
            return tasks if tasks else ["No pending tasks!"]
        except Exception as e:
            return [f"Error loading tasks: {str(e)[:20]}"]

    def get_stats(self):
        # ... (Your existing IP/CPU/RAM logic) ...
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except: ip = "Disconnected"

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        return {
            "time": datetime.now().strftime("%H:%M"),
            "date": datetime.now().strftime("%a, %b %d"),
            "ip": f"IP: {ip}",
            "stats": f"CPU: {cpu}% | RAM: {ram}%"
        }

    def update(self):
        now = datetime.now()
        
        # Only fetch tasks if the hour has changed
        if now.hour != self.last_task_update:
            print("📅 Fetching fresh tasks...")
            self.cached_tasks = self.get_tasks()
            self.last_task_update = now.hour

        data = self.get_stats()
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)

        # Draw Header (Time & Date)
        draw.text((30, 20), data["time"], font=self.time_font, fill=0)
        draw.text((30, 120), data["date"], font=self.stat_font, fill=0)

        # Draw Task List Section
        draw.line((30, 160, self.epd.width - 30, 160), fill=0, width=2)
        draw.text((30, 175), "PENDING TASKS:", font=ImageFont.truetype(FONT_PATH, 18), fill=0)
        
        y_offset = 210
        for task in self.cached_tasks:
            # Truncate long tasks
            display_text = f"• {task[:45]}..." if len(task) > 45 else f"• {task}"
            draw.text((40, y_offset), display_text, font=self.task_font, fill=0)
            y_offset += 35

        # Draw Stats Footer
        draw.line((30, 420, self.epd.width - 30, 420), fill=0, width=2)
        draw.text((30, 435), data["stats"], font=self.stat_font, fill=0)
        draw.text((self.epd.width - 200, 435), data["ip"], font=self.stat_font, fill=0)

        self.epd.display(self.epd.getbuffer(img))

    def run(self):
        # ... (Your existing run loop) ...
        while True:
            self.update()
            now = datetime.now()
            seconds_to_wait = 60 - now.second - (now.microsecond / 1000000.0)
            time.sleep(max(0, seconds_to_wait + 0.1))

if __name__ == "__main__":
    dash = PrecisionDash()
    try:
        dash.run()
    except KeyboardInterrupt:
        dash.epd.init()
        dash.epd.Clear()
        dash.epd.sleep()
