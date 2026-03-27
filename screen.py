#!/usr/bin/python
# -*- coding:utf-8 -*-
# pi_435@raspberrypi:~/e-Paper/RaspberryPi_JetsonNano/python/examples$
# https://github.com/waveshare/e-Paper.git
import os
import sys
import time
import logging
import requests
import traceback
import numpy as np
from PIL import Image, ImageEnhance

# Setup paths for Waveshare driver and fonts
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')



# Get the directory of the current script (e.g., /home/pi435/E-INK)
script_dir = os.path.dirname(os.path.realpath(__file__))

# Get the path to the 'lib' directory (e.g., /home/pi435/E-INK/lib)
lib_dir = os.path.join(script_dir, 'lib')

# Add the 'lib' directory to Python's search path
if os.path.exists(lib_dir):
    sys.path.append(lib_dir)
else:
    print(f"Error: 'lib' directory not found at {lib_dir}")
    sys.exit(1)

# --- NOW you can import the module ---
try:
    from waveshare_epd import epd7in5_V2
except ImportError:
    print("ImportError: Failed to find 'waveshare_epd'.")
    print("Please check that the 'lib' directory is correct.")
    sys.exit(1)






if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in5_V2

logging.basicConfig(level=logging.DEBUG)

epd = epd7in5_V2.EPD()
epd.init_fast()  # Or use epd.init_part() if supported


# Puppeteer backend server
SERVER_URL = "http://192.168.18.29:3000/execute"

def fetch_and_save_screenshot(script: str, command_id: int) -> str | None:
    payload = {
        "script": script,
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

def process_and_display_image_old(image_path: str):
    try:
        epd = epd7in5_V2.EPD()
        epd.init_4Gray()

        image = Image.open(image_path).convert('L')
        image = image.resize((epd.width, epd.height), Image.LANCZOS)

        # Enhance contrast
        image = ImageEnhance.Contrast(image).enhance(1.5)

        # Convert to 4-gray level numpy image
        np_img = np.array(image)
        thresholds = [63, 127, 191]
        gray_levels = [40, 85, 170, 255]
        np_img_4gray = np.digitize(np_img, thresholds, right=True)
        np_img_4gray = np.array([gray_levels[i] for i in np_img_4gray.flatten()]).reshape(np_img.shape)

        final_img = Image.fromarray(np_img_4gray.astype('uint8'), mode='L')
        epd.display_4Gray(epd.getbuffer_4Gray(final_img))

        time.sleep(2)
        epd.sleep()
    except Exception as e:
        logging.error("Failed to display image.")
        traceback.print_exc()
#
# def process_and_display_image(image_path: str):
#     try:
#         epd = epd7in5_V2.EPD()
#         #epd.init()
#         #epd.init_part()
#         epd.init_fast()
#         image = Image.open(image_path).convert('1')  # Convert to 1-bit B/W
#         #image = image.resize((epd.width, epd.height), Image.LANCZOS)
#         epd.display(epd.getbuffer(image))
#         time.sleep(1)
#         epd.sleep()
#     except Exception as e:
#         logging.error("Failed to display image.")
#         traceback.print_exc()
#


def process_and_display_image(image_path: str):
    try:
        image = Image.open(image_path).convert('1')  # Convert to 1-bit B/W
        epd.display(epd.getbuffer(image))
    except Exception as e:
        logging.error("Failed to display image.")
        traceback.print_exc()

def shutdown_display():
    epd.Clear()
    epd.sleep()

def main():
    command_id = 1
    while True:
        print("\n📥 Enter Puppeteer JS command (or type 'exit' to quit):")
        user_script = input(">>> ").strip()
        if user_script.lower() == "exit":
            print("👋 Exiting.")
            shutdown_display()
            break

        if not user_script:
            print("⚠️  Empty command, try again.")
            continue

        screenshot_path = fetch_and_save_screenshot(user_script, command_id)
        if screenshot_path:
            process_and_display_image(screenshot_path)
            command_id += 1
        else:
            print("❌ Failed to fetch or display screenshot.")

if __name__ == "__main__":
    main()
