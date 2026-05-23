#!/usr/bin/python
# -*- coding:utf-8 -*-

import json
import os
import select
import sys
import termios
import time
import tty
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE = 20
MARGIN_X = 2
MARGIN_Y = 2
FOOTER_HEIGHT = 20


class AdvancedReader:
    def __init__(self, book_path, epd):
        self.original_path = book_path

        # If the file is an FB2, parse it and create a plain text version
        if book_path.lower().endswith(".fb2"):
            self.book_path = self._convert_fb2_to_txt(book_path)
        else:
            self.book_path = book_path

        self.file_size = os.path.getsize(self.book_path)

        # Bind the EPD passed from the menu and initialize fast mode
        self.epd = epd
        self.epd.init_fast()

        # RESTORED: Unique state file per book
        self.state_file = f"{self.original_path}.state.json"

        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        self.footer_font = ImageFont.truetype(FONT_PATH, 16)

        self.current_offset = 0
        self.next_offset = 0
        self.history = [0]
        self._load_state()
        if self.current_offset == 0:
            self._skip_bom()

    def _convert_fb2_to_txt(self, fb2_path):
        """Extracts plain text from an FB2 XML file and caches it."""
        cache_path = fb2_path + ".txt.cache"
        if os.path.exists(cache_path):
            return cache_path

        print("First time opening FB2. Cleaning and converting to plain text cache...")
        with open(fb2_path, "rb") as f:
            raw_data = f.read()

        if raw_data.startswith(b"\xef\xbb\xbf"):
            raw_data = raw_data[3:]

        raw_data = raw_data.lstrip()
        root = ET.fromstring(raw_data)

        with open(cache_path, "w", encoding="utf-8") as f:
            for elem in root.iter():
                tag = elem.tag.split("}")[-1]
                if tag in ["p", "v", "subtitle", "text-author"]:
                    text = "".join(elem.itertext()).strip()
                    if text:
                        f.write(text + "\n")
                elif tag == "title":
                    f.write("\n")
                    text = "".join(elem.itertext()).strip()
                    if text:
                        f.write(text + "\n")
                    f.write("\n")
                elif tag == "empty-line":
                    f.write("\n")

        return cache_path

    # RESTORED: Original loading logic
    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    self.current_offset = json.load(f).get("offset", 0)
            except:
                self.current_offset = 0

    # RESTORED: Original saving logic
    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump({"offset": self.current_offset}, f)

    def _skip_bom(self):
        with open(self.book_path, "rb") as f:
            if f.read(3) == b"\xef\xbb\xbf":
                self.current_offset = 3

    def get_page_content(self, start_ptr):
        """Random access read and wrap."""
        with open(self.book_path, "rb") as f:
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

        lines, consumed = self.get_page_content(self.current_offset)
        self.next_offset = self.current_offset + consumed

        line_height = self.font.getbbox("Ay")[3] + 8
        for i, l in enumerate(lines):
            draw.text((MARGIN_X, MARGIN_Y + i * line_height), l, font=self.font, fill=0)

        prog = (self.current_offset / self.file_size) * 100
        footer = f"{prog:.1f}% | Offset: {self.current_offset}"
        draw.text(
            (MARGIN_X, self.epd.height - 30), footer, font=self.footer_font, fill=0
        )
        self.epd.init_fast()
        self.epd.display(self.epd.getbuffer(img))
        self.epd.sleep()

        # State saves here every time a page is rendered
        self._save_state()

    # --- Navigation Helpers ---
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

    def search(self, query):
        print(f"\nSearching for: {query}")
        with open(self.book_path, "rb") as f:
            f.seek(self.current_offset + 1)
            remaining = f.read().decode("utf-8", errors="ignore")
            idx = remaining.lower().find(query.lower())
            if idx != -1:
                self.history.append(self.current_offset)
                found_text_segment = remaining[:idx]
                self.current_offset += len(found_text_segment.encode("utf-8"))
                self.render()
            else:
                print("Not found.")

    def jump_to_percent(self, pct):
        target = int((pct / 100) * self.file_size)
        self.history.append(self.current_offset)
        self.current_offset = target
        self.render()


# --- Input Handling ---
def restore_terminal(fd, old_settings):
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def get_input_cooked(prompt, fd, old_settings):
    """Temporarily restore terminal to cooked mode to get string input."""
    restore_terminal(fd, old_settings)
    try:
        val = input("\n" + prompt)
    except:
        val = ""
    tty.setcbreak(fd)  # Go back to cbreak
    return val


# --- STANDARD ENTRY POINT FOR E-INK MENU ---
def run_app(epd, book_path):
    # epd.Clear()

    reader = AdvancedReader(book_path, epd)
    reader.render()

    print("\nControls: [D] Next  [A] Back  [T] Timer  [/] Search  [J] Jump %  [Q] Quit")

    # Setup Terminal
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    auto_timer_interval = 0  # 0 means OFF
    last_action_time = time.time()

    try:
        tty.setcbreak(fd)

        while True:
            wait_time = None
            if auto_timer_interval > 0:
                elapsed = time.time() - last_action_time
                wait_time = max(0, auto_timer_interval - elapsed)

            rlist, _, _ = select.select([sys.stdin], [], [], wait_time)

            if rlist:
                k = sys.stdin.read(1).lower()
                last_action_time = time.time()

                if k == "q":
                    break
                elif k == "d":
                    if reader.turn_page_forward():
                        termios.tcflush(sys.stdin, termios.TCIFLUSH)
                elif k == "a":
                    reader.turn_page_back()
                    termios.tcflush(sys.stdin, termios.TCIFLUSH)
                elif k == "/":
                    q = get_input_cooked("Search: ", fd, old_settings)
                    if q:
                        reader.search(q)
                elif k == "j":
                    p = get_input_cooked("Jump %: ", fd, old_settings)
                    try:
                        reader.jump_to_percent(float(p))
                    except:
                        pass
                elif k == "t":
                    t_str = get_input_cooked(
                        "Set auto-turn seconds (0 to disable): ", fd, old_settings
                    )
                    try:
                        val = float(t_str)
                        auto_timer_interval = val
                        print(f"Auto-turn set to {val}s")
                    except:
                        print("Invalid number")

            else:
                if auto_timer_interval > 0:
                    print(".", end="", flush=True)
                    reader.turn_page_forward()
                    last_action_time = time.time()

    finally:
        restore_terminal(fd, old_settings)
