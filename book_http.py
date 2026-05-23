#!/usr/bin/python
# -*- coding:utf-8 -*-

import json
import os
import select
import sys
import termios
import time
import tty
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 20
MARGIN_X = 2
MARGIN_Y = 2
FOOTER_HEIGHT = 20

TEXT_FILE = "/tmp/book2_http_preview.txt"

# Global pipes for Thread-to-Main-Loop communication
pipe_read_fd, pipe_write_fd = None, None

# --- Integrated HTTP Server ---
class WebhookHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_POST(self):
        if self.path == "/receive":
            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length)
            try:
                payload = json.loads(data.decode('utf-8'))
                text = payload.get("text", "")
                
                if text:
                    # 1. Save incoming text
                    with open(TEXT_FILE, "w", encoding="utf-8") as f:
                        f.write(text)

                    # 2. Wake up the main thread's select() loop instantly
                    if pipe_write_fd is not None:
                        os.write(pipe_write_fd, b"X")

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok"}')
                    return
            except Exception as e:
                print(f"Error processing text: {e}")

        self.send_response(400)
        self.end_headers()

    def log_message(self, format, *args):
        pass # Suppress terminal spam so the menu doesn't get messed up


# --- E-Ink Reader (Simplified for HTTP text only) ---
class HTTPReader:
    def __init__(self, epd):
        self.epd = epd
        self.epd.init_fast()
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 16)
        
        self.current_offset = 0
        self.next_offset = 0
        self.history = [0]
        self.file_size = 0
        
        if os.path.exists(TEXT_FILE):
            self.file_size = os.path.getsize(TEXT_FILE)

    def get_page_content(self, start_ptr):
        if not os.path.exists(TEXT_FILE):
            return ["Waiting for browser text..."], 0

        with open(TEXT_FILE, "rb") as f:
            f.seek(start_ptr)
            blob = f.read(6144)
            text = blob.decode("utf-8", errors="ignore")

        lines = []
        max_w = self.epd.width - (MARGIN_X * 2)
        max_y = self.epd.height - FOOTER_HEIGHT - 10
        line_height = self.font.getbbox("Ay")[3] + 8
        curr_y = MARGIN_Y

        paragraphs = text.split("\n")
        temp_img = Image.new("1", (1, 1))
        draw = ImageDraw.Draw(temp_img)

        for p in paragraphs:
            words = p.split(" ")
            line = ""
            for word in words:
                test_line = line + (" " if line else "") + word
                w = draw.textbbox((0, 0), test_line, font=self.font)[2]
                if w <= max_w:
                    line = test_line
                else:
                    lines.append(line)
                    curr_y += line_height
                    line = word
                    if curr_y + line_height > max_y:
                        break

            if curr_y + line_height > max_y:
                break
            lines.append(line)
            curr_y += line_height + 4

        displayed_text = "\n".join(lines)
        actual_bytes = len(displayed_text.encode("utf-8"))
        return lines, actual_bytes

    def render(self):
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)

        if self.file_size > 0:
            lines, consumed = self.get_page_content(self.current_offset)
            self.next_offset = self.current_offset + consumed
            prog = (self.current_offset / self.file_size) * 100 if self.file_size > 0 else 100
            footer = f"Web Snippet | {prog:.1f}% | Offset: {self.current_offset}"
        else:
            lines = [
                "HTTP Receiver Mode Active", 
                "-------------------------",
                "1. Open your browser.",
                "2. Highlight text to read.",
                "3. Right click -> Send to E-Ink.",
                "",
                "Listening on port 8080..."
            ]
            footer = "Waiting for data..."

        line_height = self.font.getbbox("Ay")[3] + 8
        for i, l in enumerate(lines):
            draw.text((MARGIN_X, MARGIN_Y + i * line_height), l, font=self.font, fill=0)

        draw.text((MARGIN_X, self.epd.height - 30), footer, font=self.footer_font, fill=0)
        
        self.epd.init_fast()
        self.epd.display(self.epd.getbuffer(img))
        self.epd.sleep()

    def turn_page_forward(self):
        if self.next_offset < self.file_size:
            self.history.append(self.current_offset)
            self.current_offset = self.next_offset
            self.render()
            return True
        return False

    def turn_page_back(self):
        if len(self.history) > 1:
            self.current_offset = self.history.pop()
            self.render()


# --- Input Handling ---
def restore_terminal(fd, old_settings):
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def get_input_cooked(prompt, fd, old_settings):
    restore_terminal(fd, old_settings)
    try:
        val = input("\n" + prompt)
    except:
        val = ""
    tty.setcbreak(fd)  
    return val


# --- ENTRY POINT FOR menu.py ---
def run_app(epd, book_path=None):
    global pipe_read_fd, pipe_write_fd
    
    # 1. Setup internal thread communication pipe
    pipe_read_fd, pipe_write_fd = os.pipe()

    # 2. Start the HTTP server on a background thread
    server = HTTPServer(('0.0.0.0', 8080), WebhookHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # 3. Setup Terminal
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    
    print("\n[book2.py] HTTP Server started on port 8080.")
    print("Send text via Chrome Extension. Ignore the file you selected in the menu.")
    print("Controls: [D]/[Right] Next  [A]/[Left] Back  [Q] Quit")

    # 4. Initialize reader (it will show the "Waiting" screen initially)
    # Clear out old HTTP text so it starts fresh every time you launch
    if os.path.exists(TEXT_FILE):
        os.remove(TEXT_FILE)
        
    reader = HTTPReader(epd)
    reader.render()

    try:
        tty.setcbreak(fd)

        while True:
            # Multiplex: Listen to terminal AND the internal HTTP thread pipe
            rlist, _, _ = select.select([sys.stdin, pipe_read_fd], [], [])

            if rlist:
                # -> Thread tells us new HTTP data has arrived
                if pipe_read_fd in rlist:
                    os.read(pipe_read_fd, 1024) # Flush the wakeup signal
                    print("\n[HTTP] Snippet received! Rendering...")
                    reader = HTTPReader(epd) # Reload the reader to grab new file size
                    reader.render()
                    continue

                # -> Keyboard Input
                k = sys.stdin.read(1)

                # Handle arrow keys (ANSI escape sequences)
                if k == '\x1b':
                    rlist2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if rlist2:
                        k2 = sys.stdin.read(1)
                        if k2 == '[':
                            k3 = sys.stdin.read(1)
                            if k3 == 'C': k = 'd' # Right arrow maps to Next
                            if k3 == 'D': k = 'a' # Left arrow maps to Back
                
                k = k.lower()

                if k == "q":
                    break # Quits back to menu
                
                elif k == "d" and reader.file_size > 0:
                    if reader.turn_page_forward():
                        termios.tcflush(sys.stdin, termios.TCIFLUSH)
                elif k == "a" and reader.file_size > 0:
                    reader.turn_page_back()
                    termios.tcflush(sys.stdin, termios.TCIFLUSH)

    finally:
        print("\nShutting down HTTP Server...")
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)
        
        os.close(pipe_read_fd)
        os.close(pipe_write_fd)
        pipe_read_fd, pipe_write_fd = None, None
        
        restore_terminal(fd, old_settings)
