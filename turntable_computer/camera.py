import subprocess


class Camera:
    # I'm assuming that only one camera, a Fuji X-T4, is connected to the RPi,
    # for other cameras the commands below may have to be changed

    def __init__(self, output_folder):
        self.output_folder = output_folder
        self.p = None

    def connect_to_camera(self):
        if self.p is not None:  # may want to do some checks to see if gphoto2 is running and connected...
            print("already connected to camera")
            return

        self.p = subprocess.Popen(["bash"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.cmd('gphoto2 --shell')
        # Todo: check if it was opened correctly

        self.change_directory(self.output_folder)

        # Camera settings, I'm using these for my Fuji cameras, may need to be
        # changed for different cameras ...
        self.original_focusmode = self.get_focus_mode()
        self.set_focus_mode("Manual")

        # self.original_is = self.get_image_stabilization()
        # self.set_image_stabilization(2)

        self.original_format = self.get_image_format()
        self.set_image_format("JPEG Fine")  # or "JPEG Normal"

        # self.original_size = self.get_image_size()
        # self.set_image_size("6240x4160")

    def shutdown(self):
        if self.p is None:
            return

        self.set_focus_mode(self.original_focusmode)
        # self.set_image_stabilization(self.original_is)
        self.set_image_format(self.original_format)
        # self.set_image_size(self.original_size)

        self.cmd('exit')  # exit gphoto2
        self.cmd('exit')  # exit shell

        self.p.wait()
        self.p = None

    def cmd(self, c):
        self.p.stdin.write(f'{c}\n'.encode('utf-8'))
        self.p.stdin.flush()

    def consume_lines(self, n):
        for _ in range(n):
            self.p.stdout.readline()

    def get_property(self, p):
        self.cmd(f"get-config {p}")
        res = None

        while True:
            l = self.p.stdout.readline().decode().strip()

            if l == 'END':
                break

            if l.startswith('Current: '):
                res = l[9:]
                # we don't break because we want to parse all data sent by
                # the camera, otherwise the unread data will mess with future
                # reads we may want to do

        return res

    def change_directory(self, d):
        self.cmd(f"lcd {d}")
        self.consume_lines(3)  # ignore output

    def get_image_format(self):
        return self.get_property("/main/imgsettings/imageformat")

    def set_image_format(self, f):
        self.cmd(f"set-config /main/imgsettings/imageformat {f}")
        self.consume_lines(2)  # ignore output

    def get_image_size(self):
        return self.get_property("/main/imgsettings/imagesize")

    def set_image_size(self, s):
        self.cmd(f"set-config /main/imgsettings/imagesize {s}")
        self.consume_lines(2)  # ignore output

    def get_focus_mode(self):
        return self.get_property("/main/capturesettings/focusmode")

    def set_focus_mode(self, m):
        self.cmd(f"set-config /main/capturesettings/focusmode {m}")

    def get_image_stabilization(self):
        # 1: continuous, 2: shooting only, 3: off
        return int(self.get_property("/main/other/d351"))

    def set_image_stabilization(self, v):
        self.cmd(f"set-config /main/other/d351 {v}")
        self.consume_lines(2)  # ignore output

    @staticmethod
    def get_focus_position_static():
        res = subprocess.check_output(['gphoto2', '--get-config', '/main/other/d171'])
        res = res.decode().splitlines()
        res = [l for l in lines if l.startswith('Current:')][0]
        return int(res[9:])

    def get_focus_position(self):
        return int(self.get_property("/main/other/d171"))

    def set_focus_position(self, p):
        self.cmd(f"set-config /main/other/d171 {p}")
        self.consume_lines(2)  # ignore output 

    def capture_image(self, focus_position=None):
        # this function tells the camera to take an image and it immediately
        # downloads it to the output folder

        if focus_position is not None:
            self.set_focus_position(focus_position)

        self.cmd("capture-image-and-download")
        self.consume_lines(3)

        l = self.p.stdout.readline().decode().strip()
        fname = l.split(' ')[-1]

        self.consume_lines(1)
        print("fname:", fname)  # may want to rename the image ...



if __name__ == '__main__':
    import time
    t_start = time.time()

    output_folder = '/home/mpr/temp/camera_test'

    c = Camera(output_folder)

    print(c.get_focus_position())
    # c.set_image_stabilization(2)

    time.sleep(3)
    c.shutdown()
    
    """
    c.set_focus_position(800)
    c.capture_image()
    """
    print("Starting loop")

    while True:
        break
        print(c.p.stdout.readline().decode().strip())


