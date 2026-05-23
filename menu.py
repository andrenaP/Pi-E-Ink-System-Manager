#!/usr/bin/python
# -*- coding:utf-8 -*-

import importlib
import os
import re
import select
import sys
import termios
import time
import tty

from PIL import Image, ImageDraw, ImageFont

# Setup Waveshare Paths
try:
    from waveshare_epd import epd7in5_V2
except (ImportError, RuntimeError):
    from epd_emulator import epd7in5_V2

    print("\n[EMULATOR] Waveshare drivers not found. Running in Window Emulator Mode!")

# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
# FONT_PATH = "font.ttf"
HEADER_SIZE = 36
ITEM_SIZE = 24
MARGIN_X = 20
MARGIN_Y = 20
RENDER_DELAY = 0.6

# SMART FILE PLANNER
APP_NEEDS_FILE = {
    "book.py": (".txt", ".fb2"),
    "book2.py": (".txt", ".fb2"),
    "image.py": (".jpg", ".jpeg", ".png"),
}


class EInkMenu:
    def __init__(self):
        self.epd = epd7in5_V2.EPD()

        self.header_font = ImageFont.truetype(FONT_PATH, HEADER_SIZE)
        self.item_font = ImageFont.truetype(FONT_PATH, ITEM_SIZE)

        self.state = "MAIN"
        self.selected_idx = 0
        self.scroll_offset = 0
        self.render_mode = "FAST"  # Added render mode state

        self.scripts = self.get_python_scripts()
        self.items = self.scripts + ["Edit Settings", "Quit"]
        self.title = "E-INK SYSTEM MANAGER"

        self.target_script = None
        self.settings_list = []

        self.typing_buffer = ""
        self.typing_prompt = ""
        self.active_conf = None

    def get_python_scripts(self):
        scripts = [
            f
            for f in os.listdir(".")
            if f.endswith(".py")
            and f not in ["menu.py", "epdconfig.py", "epd_emulator.py"]
        ]
        scripts.sort()
        return scripts

    def render(self, force_full_refresh=False):
        img = Image.new("1", (self.epd.width, self.epd.height), 255)
        draw = ImageDraw.Draw(img)

        # --- TYPING OVERLAY MODE ---
        if self.state == "TYPING":
            draw.text((MARGIN_X, MARGIN_Y), self.title, font=self.header_font, fill=0)

            box_x1, box_y1 = 50, 150
            box_x2, box_y2 = self.epd.width - 50, 350
            draw.rectangle(
                [box_x1, box_y1, box_x2, box_y2], fill=255, outline=0, width=4
            )

            draw.text(
                (box_x1 + 20, box_y1 + 20),
                self.typing_prompt,
                font=self.item_font,
                fill=0,
            )
            draw.text(
                (box_x1 + 20, box_y1 + 80),
                "Current: " + self.active_conf["value"],
                font=self.item_font,
                fill=0,
            )
            draw.text(
                (box_x1 + 20, box_y1 + 140),
                "> " + self.typing_buffer + "█",
                font=self.header_font,
                fill=0,
            )

        # --- NORMAL MENU MODE ---
        else:
            draw.text((MARGIN_X, MARGIN_Y), self.title, font=self.header_font, fill=0)

            # --- Draw Render Mode Indicator ---
            mode_text = f"[{self.render_mode}]"
            bbox = draw.textbbox((0, 0), mode_text, font=self.item_font)
            draw.text(
                (
                    self.epd.width - bbox[2] - MARGIN_X,
                    MARGIN_Y + (HEADER_SIZE - ITEM_SIZE) // 2,
                ),
                mode_text,
                font=self.item_font,
                fill=0,
            )

            draw.line(
                (
                    MARGIN_X,
                    MARGIN_Y + HEADER_SIZE + 10,
                    self.epd.width - MARGIN_X,
                    MARGIN_Y + HEADER_SIZE + 10,
                ),
                fill=0,
                width=3,
            )

            start_y = MARGIN_Y + HEADER_SIZE + 40
            line_height = ITEM_SIZE + 15
            max_visible_items = int((self.epd.height - start_y) // line_height)

            if self.selected_idx < self.scroll_offset:
                self.scroll_offset = self.selected_idx
            elif self.selected_idx >= self.scroll_offset + max_visible_items:
                self.scroll_offset = self.selected_idx - max_visible_items + 1

            for i in range(
                self.scroll_offset,
                min(len(self.items), self.scroll_offset + max_visible_items),
            ):
                display_idx = i - self.scroll_offset
                y_pos = start_y + (display_idx * line_height)
                item = self.items[i]

                if i == self.selected_idx:
                    bbox = draw.textbbox(
                        (MARGIN_X + 20, y_pos), item, font=self.item_font
                    )
                    draw.rectangle(
                        [MARGIN_X + 10, y_pos - 2, bbox[2] + 10, bbox[3] + 2], fill=0
                    )
                    draw.text(
                        (MARGIN_X + 20, y_pos), item, font=self.item_font, fill=255
                    )
                else:
                    draw.text((MARGIN_X + 20, y_pos), item, font=self.item_font, fill=0)

            if self.scroll_offset > 0:
                draw.text(
                    (self.epd.width - 40, start_y), "▲", font=self.item_font, fill=0
                )
            if self.scroll_offset + max_visible_items < len(self.items):
                draw.text(
                    (self.epd.width - 40, self.epd.height - 40),
                    "▼",
                    font=self.item_font,
                    fill=0,
                )

        # --- SMART RENDERING EXECUTION ---
        # If NORMAL mode is active, treat every refresh as a fast full refresh
        if force_full_refresh or self.render_mode == "NORMAL":
            self.epd.init_fast()  # Changed from init()
            self.epd.display(self.epd.getbuffer(img))

            # If we are in FAST mode, prep the display for the *next* partial update
            if self.render_mode == "FAST":
                self.epd.init_part()  # Changed from init_fast()
        else:
            self.epd.display_Partial(
                self.epd.getbuffer(img), 0, 0, self.epd.width, self.epd.height
            )

    def launch_app_module(self, script_name, arg=None):
        """Dynamically imports the requested script and hands it the epd hardware"""
        module_name = script_name[:-3]  # Remove .py

        # Restore standard terminal output so apps work correctly
        global old_term_settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term_settings)
        os.system("cls" if os.name == "nt" else "clear")

        # Inject the current render mode into the epd object so apps can read it
        self.epd.menu_render_mode = self.render_mode

        # Pre-initialize the display appropriately for the app
        if self.render_mode == "NORMAL":
            self.epd.init_fast()  # Changed from init()
        else:
            self.epd.init_part()  # Changed from init_fast()

        try:
            if module_name in sys.modules:
                app = importlib.reload(sys.modules[module_name])
            else:
                app = importlib.import_module(module_name)
            if hasattr(app, "run_app"):
                if arg:
                    app.run_app(self.epd, arg)
                else:
                    app.run_app(self.epd)
            else:
                print(f"Error: {script_name} is missing a 'run_app(epd)' function!")
                time.sleep(3)

        except Exception as e:
            print(f"App crashed: {e}")
            time.sleep(3)

        # App exited! Re-claim the keyboard and refresh the menu
        tty.setraw(sys.stdin)
        self.render(force_full_refresh=True)

    def handle_enter(self):
        if self.state == "MAIN":
            selection = self.items[self.selected_idx]

            if selection == "Quit":
                return False

            elif selection == "Edit Settings":
                self.state = "SETTINGS_SCRIPT_SELECT"
                self.title = "Select App to Edit:"
                self.items = self.scripts + ["Back"]
                self.selected_idx = 0
                self.scroll_offset = 0
                self.render()

            elif selection in APP_NEEDS_FILE:
                self.target_script = selection
                allowed_exts = APP_NEEDS_FILE[selection]
                found_files = [
                    f
                    for f in os.listdir(".")
                    if f.lower().endswith(allowed_exts)
                    and f.lower() != "requirements.txt"
                ]

                self.items = (
                    found_files if found_files else [f"No {allowed_exts} files found!"]
                )
                self.items.append("Back")
                self.title = f"Select file for {selection}:"
                self.state = "FILE_SELECT"
                self.selected_idx = 0
                self.scroll_offset = 0
                self.render()

            else:
                self.launch_app_module(selection)

        elif self.state == "FILE_SELECT":
            selection = self.items[self.selected_idx]
            if selection == "Back":
                self._reset_to_main()
            elif selection.startswith("No "):
                pass
            else:
                self.launch_app_module(self.target_script, selection)
                self._reset_to_main()

        elif self.state == "SETTINGS_SCRIPT_SELECT":
            selection = self.items[self.selected_idx]
            if selection == "Back":
                self._reset_to_main()
            else:
                self.target_script = selection
                self._load_settings_for_edit(selection)

        elif self.state == "SETTINGS_EDIT":
            selection = self.items[self.selected_idx]
            if selection == "Back":
                self.state = "SETTINGS_SCRIPT_SELECT"
                self.title = "Select App to Edit:"
                self.items = self.scripts + ["Back"]
                self.selected_idx = 0
                self.scroll_offset = 0
                self.render()
            else:
                self.active_conf = self.settings_list[self.selected_idx]
                self.typing_buffer = ""
                self.typing_prompt = f"New value for {self.active_conf['name']}:"
                self.state = "TYPING"
                self.render()

        return True

    def _load_settings_for_edit(self, script_name):
        try:
            with open(script_name, "r") as f:
                self.target_lines = f.readlines()
        except:
            return

        config_pattern = re.compile(r"^([A-Z_0-9]+)\s*=\s*(.+)$")
        self.settings_list = []
        self.items = []

        for i, line in enumerate(self.target_lines):
            match = config_pattern.match(line.strip())
            if match:
                name, val = match.group(1), match.group(2)
                self.settings_list.append({"line_num": i, "name": name, "value": val})
                self.items.append(f"{name} = {val}")

        self.items.append("Back")
        self.title = f"Edit: {script_name}"
        self.state = "SETTINGS_EDIT"
        self.selected_idx = 0
        self.scroll_offset = 0
        self.render()

    def _save_setting(self, new_value):
        self.target_lines[self.active_conf["line_num"]] = (
            f"{self.active_conf['name']} = {new_value}\n"
        )
        with open(self.target_script, "w") as f:
            f.writelines(self.target_lines)

    def _reset_to_main(self):
        self.state = "MAIN"
        self.title = "E-INK SYSTEM MANAGER"
        self.scripts = self.get_python_scripts()
        self.items = self.scripts + ["Edit Settings", "Quit"]
        self.selected_idx = 0
        self.scroll_offset = 0
        self.render()


def get_key():
    ch = sys.stdin.read(1)
    if ch == "\x1b":
        ch2 = sys.stdin.read(1)
        if ch2 == "[":
            ch3 = sys.stdin.read(1)
            if ch3 == "A":
                return "UP"
            if ch3 == "B":
                return "DOWN"
            if ch3 == "C":
                return "RIGHT"
            if ch3 == "D":
                return "LEFT"
    if ch == "\r" or ch == "\n":
        return "ENTER"
    if ch == "\x7f" or ch == "\b":
        return "BACKSPACE"
    return ch


if __name__ == "__main__":
    old_term_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setraw(sys.stdin)
        menu = EInkMenu()
        menu.render(force_full_refresh=True)

        needs_render = False
        force_refresh_next = False
        last_key_time = time.time()

        while True:
            # select with a small timeout keeps the loop running to check the clock
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)

            if rlist:
                key = get_key()
                last_key_time = time.time()  # Reset the clock on every keypress

                if menu.state == "TYPING":
                    if key == "ENTER":
                        if menu.typing_buffer.strip():
                            menu._save_setting(menu.typing_buffer)
                        menu._load_settings_for_edit(menu.target_script)
                        needs_render = True
                    elif key == "BACKSPACE":
                        menu.typing_buffer = menu.typing_buffer[:-1]
                        needs_render = True
                    elif len(key) == 1 and key.isprintable():
                        menu.typing_buffer += key
                        needs_render = True
                    continue

                if key == "UP" or key.lower() in ["w", "k"]:
                    if menu.selected_idx > 0:
                        menu.selected_idx -= 1
                        needs_render = True
                elif key == "DOWN" or key.lower() in ["s", "j"]:
                    if menu.selected_idx < len(menu.items) - 1:
                        menu.selected_idx += 1
                        needs_render = True
                elif key.lower() == "r":
                    # --- TOGGLE RENDER MODE HOTKEY ---
                    menu.render_mode = (
                        "NORMAL" if menu.render_mode == "FAST" else "FAST"
                    )
                    needs_render = True
                    force_refresh_next = True
                elif key == "ENTER":
                    keep_running = menu.handle_enter()
                    if not keep_running:
                        break
                elif key == "QUIT" or key.lower() == "q":
                    if menu.state == "MAIN":
                        break  # Quit the app only if we are on the main menu
                    elif menu.state in ["FILE_SELECT", "SETTINGS_SCRIPT_SELECT"]:
                        menu._reset_to_main()  # Go back to main
                    elif menu.state == "SETTINGS_EDIT":
                        # Go back to the script selection screen
                        menu.state = "SETTINGS_SCRIPT_SELECT"
                        menu.title = "Select App to Edit:"
                        menu.items = menu.scripts + ["Back"]
                        menu.selected_idx = 0
                        menu.scroll_offset = 0
                        menu.render()

            # --- DELAYED RENDERING ---
            # Only render if something changed AND the delay time has passed
            if needs_render and (time.time() - last_key_time) > RENDER_DELAY:
                menu.render(force_full_refresh=force_refresh_next)
                needs_render = False
                force_refresh_next = False

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term_settings)
        os.system("cls" if os.name == "nt" else "clear")
        print("Releasing E-ink Display...")
        menu.epd.init()
        menu.epd.Clear()
        menu.epd.sleep()
        print("Menu Closed.")
