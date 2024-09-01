import time
import sys
import os

from settings import Settings
from commander import Commander
from navigator import Navigator
from camera import Camera


if __name__ == '__main__':
    s = Settings()

    formatted_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    s.output_folder = os.path.join(s.output_folder, formatted_time)
    print("Output Folder:", s.output_folder)

    cam = Camera(s.output_folder)
    nav = Navigator(s.port, s.baud_rate)
    com = Commander(s, cam, nav)

    time.sleep(2)  # need to give arduino some time to get ready
    nav.initialize()
    cmd = None


    while True:
        if cmd is None:
            cmd = input("Command: ")
            cmd = com.parse_command(cmd)

            if cmd is None:
                print("Invalid command.")
                continue

            com.run(cmd)

        else:
            cnt = input("Same command again? ")

            if cnt in ['y', 'Y', 'yes', '']:
                com.run(cmd)

            else:
                cmd = None
                continue
