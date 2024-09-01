from photographer import Photographer


def convert_to_float(n):
    try:
        return float(n)
    except ValueError:
        return None


def convert_to_int(n):
    try:
        return int(n)
    except ValueError:
        return None



class Commander:
    DEFAULT_RPM = 15

    def __init__(self, settings, camera, navigator):
        self.settings = settings
        self.cam = camera
        self.nav = navigator
        self.photographer = None

    def parse_command(self, cmd):
        # allowed commands are:
        #  V [velocity], e.g. "V 10", makes one circle at velocity 10, if no velocity is given then the DEFAULT_RPM is used
        #  P [n_photos] [velocity], e.g. "P 15 10" takes 15 equisistant photos, turntable moves at velocity (optional) 10
        cmd = cmd.split(' ')
        
        if len(cmd) == 0:
            return None

        c = cmd[0]

        if c in ['v', 'V']:
            if len(cmd) not in [1, 2]:
                return None

            if len(cmd) == 2:
                v = convert_to_float(cmd[1])

                if v is None:  # invalid velocity
                    return None
                
                return [c, v]

            return [c, Commander.DEFAULT_RPM]

        if c in ['p', 'P']:
            if len(cmd) not in [2, 3]:
                return None

            n_photos = convert_to_int(cmd[1])

            if n_photos is None:
                return None

            if len(cmd) == 3:
                v = convert_to_float(cmd[2])

                if v is None:
                    return None

                return [c, n_photos, v]

            return [c, n_photos, Commander.DEFAULT_RPM]

        if c in ['exit', 'e', 'quit', 'q']:
            self.cam.shutdown()
            self.nav.shutdown()

            import sys
            sys.exit()

        return None

    def run(self, cmd):
        if cmd[0] in ['v', 'V']:
            self.nav.set_velocity(cmd[1])
            return

        if cmd[0] in ['p', 'P']:
            if self.photographer is None:
                self.photographer = Photographer(self.settings, self.cam, self.nav)

            self.photographer.run(cmd[1], cmd[2])
