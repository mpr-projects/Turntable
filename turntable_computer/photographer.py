import os
import threading
import queue
import time
import numpy as np


class Photographer(threading.Thread):

    def __init__(self, settings, camera, navigator):
        super().__init__()
        self.settings = settings
        self.camera = camera
        self.nav = navigator
        self.stop = False

    def take_photo(self):
        print("Taking a Picture") # Todo: deal with focus bracketing
        time.sleep(self.settings.pre_foto_sleep)
        self.camera.capture_image()

    def run(self, n_photos, v):
        print(f'Photographer, n_photos={n_photos}, v={v}')
        os.makedirs(self.settings.output_folder, exist_ok=True)
        positions = [self.settings.end_position / n_photos * i for i in range(n_photos)]

        # start from closest end point
        position = self.nav.get_position()
        d_start = abs(position)
        d_end = abs(position - self.settings.end_position)

        if d_end < d_start:
            positions = positions[::-1]

        self.camera.connect_to_camera()
        
        idx = 0
        waiting_for_position = False
        
        while True:
            time.sleep(0.01)

            if self.stop is True:
                self.nav.stop()
                return

            if waiting_for_position is True:
                try:
                    res = self.nav.q_receive.get(block=False)

                    if res == 'P':  # position has been reached
                        waiting_for_position = False
                        self.take_photo()
                        idx += 1
                        print(f"Took photo {idx}/{len(positions)}.")

                except queue.Empty:
                    continue

            if idx == len(positions):
                print("Finished Taking Photos")
                print("Exiting Photographer")
                return

            # move to next position
            pos = int(round(positions[idx]))
            print("Moving to next Position:", pos)
            self.nav.set_position(pos, v)
            waiting_for_position = True
