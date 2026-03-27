#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import sys
import logging
from PIL import Image, ImageOps, ImageEnhance

# Setup Paths
script_dir = os.path.dirname(os.path.realpath(__file__))
lib_dir = os.path.join(script_dir, 'lib')
if os.path.exists(lib_dir):
    sys.path.append(lib_dir)

from waveshare_epd import epd7in5_V2 
from waveshare_epd import epdconfig

logging.basicConfig(level=logging.INFO)

class GrayArt:
    def __init__(self):
        self.width = 800
        self.height = 480
        self.epd = epd7in5_V2.EPD()

    def process_image(self, path, method="dither"):
        img = Image.open(path).convert('L')
        img = img.resize((self.width, self.height), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        
        if method == "dither":
            # METHOD 1: Floyd-Steinberg Dithering
            # This makes the image look "photographic" using tiny dots
            img = img.quantize(colors=4, method=Image.FLOYDSTEINBERG).convert('L')
            
        elif method == "high_contrast":
            # METHOD 2: Hard 4-Tone
            # Best for Manga or Comics
            img = ImageEnhance.Contrast(img).enhance(2.0)
            img = ImageOps.autocontrast(img, cutoff=2)
            img = img.quantize(colors=4, method=None).convert('L')
            
        elif method == "soft":
            # METHOD 3: Natural Gradient
            # Best for portraits
            img = ImageEnhance.Brightness(img).enhance(1.1)
            img = ImageOps.autocontrast(img)
            
        return img

    def render(self, path, method="dither"):
        img = self.process_image(path, method)
        
        # Hardware Cycle
        logging.info(f"Using Method: {method}")
        self.epd.init_4Gray()
        
        buffer = self.epd.getbuffer_4Gray(img)
        self.epd.display_4Gray(buffer)
        
        self.epd.sleep()
        print(f"✅ Rendered with {method}. Safe to unplug.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 image.py file.jpg [dither|high_contrast|soft]")
    else:
        method = sys.argv[2] if len(sys.argv) > 2 else "dither"
        GrayArt().render(sys.argv[1], method)
