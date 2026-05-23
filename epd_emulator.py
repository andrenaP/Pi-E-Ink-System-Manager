#!/usr/bin/python
# -*- coding:utf-8 -*-
import threading
import time

from PIL import Image, ImageOps

# --- Emulator Configuration ---
REALISTIC_EMULATION = False  # Set to False for instant, pure B&W updates without delays


class MockEPD:
    def __init__(self):
        self.width = 800
        self.height = 480
        self.latest_image = None
        self.refresh_type = "FULL"
        self._update_event = threading.Event()

        # Start the viewer in a background daemon thread
        self._viewer_thread = threading.Thread(target=self._run_viewer, daemon=True)
        self._viewer_thread.start()

    def _run_viewer(self):
        try:
            import tkinter as tk

            from PIL import ImageTk
        except ImportError:
            print("[EMULATOR] Tkinter missing. Fallback to saving 'epd_emulator.png'")
            self.fallback = True
            return

        self.fallback = False
        root = tk.Tk()

        # Change window title based on mode
        title_suffix = "(Realistic Mode)" if REALISTIC_EMULATION else "(Instant Mode)"
        root.title(f"E-Ink Emulator {title_suffix} - Press keys in Terminal!")
        root.geometry(f"{self.width}x{self.height}")

        # Authentic Waveshare V2 Colors
        ink_color = "#1A1A1A"  # Charcoal / Off-black
        paper_color = "#E8E8E8"  # Matte light grey

        # If not realistic, just use pure white background
        bg_color = paper_color if REALISTIC_EMULATION else "white"
        root.configure(bg=bg_color)
        label = tk.Label(root, bg=bg_color)
        label.pack(fill=tk.BOTH, expand=True)

        # Keep track of the last frame for ghosting simulation
        self.previous_frame = None

        def update_loop():
            if self._update_event.is_set() and self.latest_image:
                self._update_event.clear()

                if REALISTIC_EMULATION:
                    # Apply realistic E-ink colors for the final image
                    colored_img = ImageOps.colorize(
                        self.latest_image.convert("L"),
                        black=ink_color,
                        white=paper_color,
                    )

                    if self.refresh_type == "FULL":
                        # 1. Render the text in negative
                        negative_img = ImageOps.colorize(
                            self.latest_image.convert("L"),
                            black=paper_color,
                            white=ink_color,
                        )
                        negative_tk = ImageTk.PhotoImage(negative_img)
                        label.config(image=negative_tk)
                        label.image = negative_tk
                        root.update()
                        time.sleep(0.3)  # Wait while inverted

                        # 2. Return to solid white (clear the capsules)
                        img_white = ImageTk.PhotoImage(
                            Image.new("RGB", (self.width, self.height), paper_color)
                        )
                        label.config(image=img_white)
                        label.image = img_white
                        root.update()
                        time.sleep(0.3)  # Settling time before final render

                    elif self.refresh_type == "PARTIAL" and self.previous_frame:
                        # Simulate ghosting by blending 5% of the old image into the new one
                        colored_img = Image.blend(
                            colored_img, self.previous_frame, alpha=0.05
                        )

                    # Render final image
                    self.previous_frame = colored_img.copy()
                    final_tk = ImageTk.PhotoImage(colored_img)
                    label.config(image=final_tk)
                    label.image = final_tk

                else:
                    # INSTANT MODE: No delays, pure B&W, no flashes or ghosting
                    final_tk = ImageTk.PhotoImage(self.latest_image.convert("RGB"))
                    label.config(image=final_tk)
                    label.image = final_tk

            root.after(50, update_loop)

        update_loop()
        root.mainloop()

    # Hardware Init/Sleep methods
    def init(self):
        pass

    def init_fast(self):
        pass

    def init_part(self):
        pass

    def Clear(self):
        pass

    def sleep(self):
        pass

    def getbuffer(self, image):
        return image

    def display(self, image):
        if getattr(self, "fallback", False):
            image.save("epd_emulator.png")
        else:
            self.latest_image = image.copy()
            self.refresh_type = "FULL"
            self._update_event.set()

            if REALISTIC_EMULATION:
                # Simulate the physical time it takes the Raspberry Pi to send the SPI data
                time.sleep(0.8)

    def display_Partial(self, image, x, y, w, h):
        self.latest_image = image.copy()
        self.refresh_type = "PARTIAL"
        self._update_event.set()

        if REALISTIC_EMULATION:
            # Partial updates are much faster over SPI
            time.sleep(0.15)


class epd7in5_V2:
    EPD = MockEPD
