#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import time
import logging
import requests
import traceback
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import tty
import termios

# Setup paths for Waveshare driver and fonts
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2

logging.basicConfig(level=logging.DEBUG)

# Initialize EPD globally
epd = epd7in5_V2.EPD()
try:
    epd.init_fast()
except Exception as e:
    logging.error(f"Failed to initialize EPD: {e}")
    raise

# Puppeteer backend server
SERVER_URL = "http://192.168.0.249:3000/execute"

# Font for text display (adjust path as needed)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Example font path
FONT_SIZE = 20
FOOTER_FONT_SIZE = 16
try:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    footer_font = ImageFont.truetype(FONT_PATH, FOOTER_FONT_SIZE)
except Exception as e:
    logging.error(f"Failed to load font {FONT_PATH}: {e}")
    raise

# Chunk size (number of lines per chunk)
CHUNK_SIZE_LINES = 1000

# Save file for reading positions
SAVE_FILE = "reading_positions.json"

def split_into_chunks(text):
    """Split text into chunks based on line count."""
    lines = text.splitlines()
    chunks = []
    for i in range(0, len(lines), CHUNK_SIZE_LINES):
        chunks.append('\n'.join(lines[i:i + CHUNK_SIZE_LINES]))
    return chunks

def prewrap_text(text, font, max_width, draw_dummy):
    """Wrap text into lines, preserving paragraph breaks."""
    lines = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")  # Preserve empty lines
            continue
        words = paragraph.split()
        line = ""
        for word in words:
            test_line = line + ("" if line == "" else " ") + word
            bbox = draw_dummy.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                line = test_line
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines

def generate_page(wrapped_lines, page_number, total_pages, display_size=(800, 480), margin=10, line_spacing=4):
    """Generate a single page from prewrapped lines, with footer."""
    width, height = display_size
    lines_per_page = (height - 2 * margin - FOOTER_FONT_SIZE - 10) // (FONT_SIZE + line_spacing)  # Adjust for footer
    if page_number < 1 or page_number > total_pages:
        return None, total_pages

    start_idx = (page_number - 1) * lines_per_page
    end_idx = start_idx + lines_per_page
    page_lines = wrapped_lines[start_idx:end_idx]

    img = Image.new("1", (width, height), 255)
    draw = ImageDraw.Draw(img)
    y = margin
    line_height = FONT_SIZE + line_spacing

    for line in page_lines:
        draw.text((margin, y), line, font=font, fill=0)
        y += line_height

    # Add footer: page number and current time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    footer_text = f"Page {page_number}/{total_pages} | {current_time}"
    bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
    footer_width = bbox[2] - bbox[0]
    draw.text(((width - footer_width) // 2, height - margin - FOOTER_FONT_SIZE), footer_text, font=footer_font, fill=0)

    return img, total_pages

def fetch_and_save_screenshot(script: str, command_id: int) -> str | None:
    """Fetch and save a screenshot from the Puppeteer server."""
    full_script = f"await page.setViewport({{ width: 800, height: 480 }}); {script}"
    payload = {
        "script": full_script,
        "commandId": command_id
    }
    try:
        response = requests.post(SERVER_URL, json=payload)
        if response.status_code == 200:
            filename = f"screenshot_{command_id}.bmp"
            with open(filename, "wb") as f:
                f.write(response.content)
            logging.info(f"Screenshot saved: {filename}")
            return filename
        else:
            logging.error(f"Server error: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Request failed: {e}")
        return None

def process_and_display_image(image_path: str):
    """Display a screenshot on the e-Paper display."""
    try:
        epd.init_fast()
        image = Image.open(image_path)
        logging.info(f"Original image dimensions: {image.size}")
        image = image.convert('1').resize((epd.width, epd.height), Image.LANCZOS)
        logging.info(f"Resized image dimensions: {image.size}")
        epd.display(epd.getbuffer(image))
        time.sleep(1)
        epd.sleep()
    except Exception as e:
        logging.error(f"Failed to display image: {e}")
        traceback.print_exc()
    finally:
        try:
            epd.sleep()
        except Exception as e:
            logging.error(f"Failed to put display to sleep: {e}")

def display_text_page(page_image):
    """Display a text page on the e-Paper display."""
    try:
        epd.init_fast()
        epd.display(epd.getbuffer(page_image))
        time.sleep(1)
        epd.sleep()
    except Exception as e:
        logging.error(f"Failed to display text page: {e}")
        traceback.print_exc()
    finally:
        try:
            epd.sleep()
        except Exception as e:
            logging.error(f"Failed to put display to sleep: {e}")

def read_text_file(file_path: str) -> str:
    """Read a text file and return its contents."""
    if not file_path.endswith('.txt'):
        logging.warning(f"File {file_path} is not a .txt file. It may not display correctly.")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Failed to read text file {file_path}: {e}")
        return ""

def load_reading_position(file_path: str) -> int:
    """Load the last reading position (page number) for the file."""
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r') as f:
            positions = json.load(f)
            return positions.get(file_path, 1)
    return 1

def save_reading_position(file_path: str, page_number: int):
    """Save the current reading position (page number) for the file."""
    positions = {}
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r') as f:
            positions = json.load(f)
    positions[file_path] = page_number
    with open(SAVE_FILE, 'w') as f:
        json.dump(positions, f)

def shutdown_display():
    """Clear the display and put it to sleep."""
    try:
        epd.init_fast()
        epd.Clear()
        epd.sleep()
    except Exception as e:
        logging.error(f"Failed to clear display: {e}")

def text_mode(file_path: str):
    """Text mode: Display paginated text with keyboard navigation."""
    text = read_text_file(file_path)
    if not text:
        print("❌ Failed to read text file. Returning to mode selection.")
        return

    # Split text into chunks
    chunks = split_into_chunks(text)
    if not chunks:
        print("❌ No text to display. Check text content.")
        return

    current_chunk_idx = 0
    current_page = load_reading_position(file_path)
    wrapped_lines = None
    total_pages = 0
    draw_dummy = ImageDraw.Draw(Image.new("1", (1, 1)))
    max_text_width = epd.width - 20  # margin * 2

    def load_chunk(chunk_idx):
        """Load and wrap lines for the specified chunk."""
        nonlocal wrapped_lines, total_pages
        if 0 <= chunk_idx < len(chunks):
            wrapped_lines = prewrap_text(chunks[chunk_idx], font, max_text_width, draw_dummy)
            lines_per_page = (epd.height - 20 - FOOTER_FONT_SIZE - 10) // (FONT_SIZE + 4)  # Adjust for footer
            total_pages = (len(wrapped_lines) + lines_per_page - 1) // lines_per_page
            return True
        return False

    # Load the initial chunk based on saved page
    lines_per_page = (epd.height - 20 - FOOTER_FONT_SIZE - 10) // (FONT_SIZE + 4)
    current_chunk_idx = (current_page - 1) // lines_per_page
    load_chunk(current_chunk_idx)
    current_page = current_page - (current_chunk_idx * lines_per_page)
    if current_page < 1 or current_page > total_pages:
        current_page = 1

    page_image, total_pages = generate_page(wrapped_lines, current_page, total_pages)
    if page_image is None:
        print("❌ No text to display in first chunk. Check content or font.")
        return
    display_text_page(page_image)
    print(f"📖 Displaying page {current_page}/{total_pages} (Chunk {current_chunk_idx + 1}/{len(chunks)})")
    print("Controls: 'a' - next page, 'z' - previous page, '/' + page number + Enter - jump to page, 'q' - quit")

    # Set stdin to raw mode for single char input
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())

        jump_mode = False
        page_input = ""

        while True:
            char = sys.stdin.read(1)
            if char.lower() == 'q':
                print("\n👋 Exiting text mode.")
                # Save position before exiting
                global_page = (current_chunk_idx * lines_per_page) + current_page
                save_reading_position(file_path, global_page)
                break
            elif char.lower() == 'a':
                if current_page < total_pages:
                    current_page += 1
                else:
                    # Try loading next chunk
                    if load_chunk(current_chunk_idx + 1):
                        current_chunk_idx += 1
                        current_page = 1
                    else:
                        current_page = 1  # Reset to first page
                        current_chunk_idx = 0
                        load_chunk(current_chunk_idx)
                page_image, total_pages = generate_page(wrapped_lines, current_page, total_pages)
                display_text_page(page_image)
                print(f"\r📖 Displaying page {current_page}/{total_pages} (Chunk {current_chunk_idx + 1}/{len(chunks)})", end='')
            elif char.lower() == 'z':
                if current_page > 1:
                    current_page -= 1
                else:
                    # Try loading previous chunk
                    if load_chunk(current_chunk_idx - 1):
                        current_chunk_idx -= 1
                        current_page = total_pages  # Last page of previous chunk
                    else:
                        current_page = total_pages  # Stay on last page
                    load_chunk(current_chunk_idx)
                page_image, total_pages = generate_page(wrapped_lines, current_page, total_pages)
                display_text_page(page_image)
                print(f"\r📖 Displaying page {current_page}/{total_pages} (Chunk {current_chunk_idx + 1}/{len(chunks)})", end='')
            elif char == '/':
                jump_mode = True
                page_input = ""
                print("\rEnter page number: ", end='')
            elif jump_mode:
                if char == '\r' or char == '\n':  # Enter key
                    try:
                        target_page = int(page_input)
                        target_chunk_idx = (target_page - 1) // lines_per_page
                        chunk_page = (target_page - 1) % lines_per_page + 1
                        if 0 <= target_chunk_idx < len(chunks) and chunk_page >= 1:
                            if target_chunk_idx != current_chunk_idx:
                                current_chunk_idx = target_chunk_idx
                                load_chunk(current_chunk_idx)
                            current_page = chunk_page
                            page_image, total_pages = generate_page(wrapped_lines, current_page, total_pages)
                            if page_image:
                                display_text_page(page_image)
                                print(f"\r📖 Displaying page {current_page}/{total_pages} (Chunk {current_chunk_idx + 1}/{len(chunks)})", end='')
                            else:
                                print(f"\rInvalid page number. Must be between 1 and {total_pages}.", end='')
                        else:
                            print(f"\rInvalid page number. Must be between 1 and {len(chunks) * lines_per_page}.", end='')
                    except ValueError:
                        print("\rInvalid input. Enter a number.", end='')
                    jump_mode = False
                else:
                    page_input += char
                    print(f"\rEnter page number: {page_input}", end='')

    except KeyboardInterrupt:
        print("\n👋 Exiting text mode.")
        # Save position on interrupt
        global_page = (current_chunk_idx * lines_per_page) + current_page
        save_reading_position(file_path, global_page)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        shutdown_display()

def screenshot_mode():
    """Screenshot mode: Fetch and display Puppeteer screenshots."""
    command_id = 1
    while True:
        print("\n📥 Enter Puppeteer JS command (or type 'exit' to quit):")
        user_script = input(">>> ").strip()
        if user_script.lower() == "exit":
            print("👋 Exiting screenshot mode.")
            shutdown_display()
            break

        if not user_script:
            print("⚠️ Empty command, try again.")
            continue

        screenshot_path = fetch_and_save_screenshot(user_script, command_id)
        if screenshot_path:
            process_and_display_image(screenshot_path)
            command_id += 1
        else:
            print("❌ Failed to fetch or display screenshot.")

def main():
    """Main program loop for mode selection."""
    while True:
        print("\n📋 Select mode: 'screenshot' (for Puppeteer screenshots) or 'text' (for paginated text display). Type 'exit' to quit.")
        mode = input(">>> ").strip().lower()
        if mode == "exit":
            print("👋 Exiting.")
            shutdown_display()
            break
        elif mode == "screenshot":
            screenshot_mode()
        elif mode == "text":
            print("📄 Enter path to text file (e.g., 'input.txt'):")
            file_path = input(">>> ").strip()
            if not os.path.exists(file_path):
                print(f"❌ File {file_path} does not exist. Try again.")
                continue
            text_mode(file_path)
        else:
            print("⚠️ Invalid mode. Choose 'screenshot' or 'text'.")

if __name__ == "__main__":
    try:
        main()
    finally:
        pass
