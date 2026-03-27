#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import logging
from PIL import Image, ImageOps, ImageEnhance

# Setup Paths for config
script_dir = os.path.dirname(os.path.realpath(__file__))
lib_dir = os.path.join(script_dir, 'lib')
if os.path.exists(lib_dir):
    sys.path.append(lib_dir)

from waveshare_epd import epdconfig
from waveshare_epd import epd7in5_V2 # We use this for basic constants

logging.basicConfig(level=logging.INFO)

class Nitro4Gray:
    def __init__(self):
        self.width = 800
        self.height = 480
        self.epd = epd7in5_V2.EPD()

    def init_4Gray(self):
        """Direct hardware initialization for 4-Gray mode"""
        epdconfig.module_init()
        self.epd.reset()
        self.epd.send_command(0X00) # PANNEL SETTING
        self.epd.send_data(0x1F) 
        self.epd.send_command(0X50)
        self.epd.send_data(0x10)
        self.epd.send_data(0x07)
        self.epd.send_command(0x04) # POWER ON
        epdconfig.delay_ms(100)
        self.epd.ReadBusy()
        self.epd.send_command(0x06) # Booster Soft Start
        self.epd.send_data(0x27)
        self.epd.send_data(0x27)
        self.epd.send_data(0x18)
        self.epd.send_data(0x17)
        self.epd.send_command(0xE0)
        self.epd.send_data(0x02)
        self.epd.send_command(0xE5)
        self.epd.send_data(0x5F)
        return 0

    def render_and_sleep(self, image_path):
        if not os.path.exists(image_path):
            logging.error(f"File {image_path} not found.")
            return

        # 1. Process Image
        img = Image.open(image_path).convert('L')
        img = img.resize((self.width, self.height), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        img = ImageOps.autocontrast(img)
        
        # 2. Hardware Start
        self.init_4Gray()
        
        # 3. Display (Using the 4-Gray buffer logic from your provided code)
        logging.info("Writing 4-Gray data to screen...")
        buffer = self.epd.getbuffer_4Gray(img)
        self.epd.display_4Gray(buffer)
        
        # 4. Critical Discharge and Sleep
        logging.info("Discharging panel and entering deep sleep...")
        self.epd.sleep()
        print("\n✅ IMAGE LOCKED. You can now safely disconnect the Raspberry Pi.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 image.py your_image.jpg")
    else:
        reader = Nitro4Gray()
        reader.render_and_sleep(sys.argv[1])
