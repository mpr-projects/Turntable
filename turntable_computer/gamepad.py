import inputs
from photographer import Photographer


# the inputs library doesn't readily allow for rescanning the list of available
# gamepads, below is a workaround from https://github.com/zeth/inputs/issues/66
inputs.EVENT_MAP = (
    ('types', inputs.EVENT_TYPES),
    ('type_codes', tuple((value, key) for key, value in inputs.EVENT_TYPES)),
    ('wincodes', inputs.WINCODES),
    ('specials', inputs.SPECIAL_DEVICES),
    ('xpad', inputs.XINPUT_MAPPING),
    ('Sync', inputs.SYNCHRONIZATION_EVENTS),
    ('Key', inputs.KEYS_AND_BUTTONS),
    ('Relative', inputs.RELATIVE_AXES),
    ('Absolute', inputs.ABSOLUTE_AXES),
    ('Misc', inputs.MISC_EVENTS),
    ('Switch', inputs.SWITCH_EVENTS),
    ('LED', inputs.LEDS),
    ('LED_type_codes', inputs.LED_TYPE_CODES),
    ('Sound', inputs.SOUNDS),
    ('Repeat', inputs.AUTOREPEAT_VALUES),
    ('ForceFeedback', inputs.FORCE_FEEDBACK),
    ('Power', inputs.POWER),
    ('ForceFeedbackStatus', inputs.FORCE_FEEDBACK_STATUS),
    ('Max', inputs.MAX),
    ('Current', inputs.CURRENT))

# an alternative would be to reimport the entire inputs library (which is
# probably less efficient) with
#  - from importlib import reload
#  - reload(inputs)


class Gamepad:
    def __init__(self, settings, camera, navigator):
        self.settings = settings
        self.camera = camera
        self.nav = navigator

        self.photographer = None
        self.is_taking_photos = False

        self.get_gamepad()

        self._cam_speed = 0
        self._circ_speed = 0
        self._height_up_speed = 0
        self._height_down_speed = 0
        self._radial_forward_speed = 0
        self._radial_backward_speed = 0

    def get_gamepad(self):
        try:  # refresh list of inputs
            inputs.devices = inputs.DeviceManager()

        # this error comes up sometimes, probably due to timing issues,
        # it does resolve itself quickly ... (didn't look into details)
        except FileNotFoundError as e:
            if e.errno == 2:
                self.gamepad = None
                return

            raise e

        try:  # try to get the first gamepad
            self.gamepad = inputs.devices.gamepads[0]
            print("Gamepad connected")
        except IndexError:
            self.gamepad = None

    def process_events(self):
        try:
            events = self.gamepad.read()
        except EOFError:  # no events available
            events = []
        except AttributeError:  # if self.gamepad is None then .read() will give an AttributeError
            self.get_gamepad()  # try to get a gamepad, leave event processing for next loop iteration
            return
        except OSError as e:
            if e.errno == 19:  # this error occurs when the gamepad has been disconnected
                print("Gamepad disconnected")
                self.get_gamepad()
                return
            else:
                raise e

        # if we're currently homing or taking photos then most gamepad controls
        # should be ignored
        if self.nav.is_homing is True:
            self.nav.check_homing_status()
            allowed_codes = self.settings.allowed_codes_during_homing

        elif self.is_taking_photos is True:
            if self.photographer.is_alive():  # still running
                allowed_codes = self.settings.allowed_codes_during_taking_photos
            else:  # finished
                self.photographer = None
                self.is_taking_photos = False
                print("Photographer finished")
                # Todo: may want to notify user (beeping?), may want to turn object upside down (or that maybe as part of the Photographer...)

        # process events
        for event in events:
            if event.ev_type == 'Sync' or event.ev_type == 'Misc':
                continue

            if event.code not in self.settings.gamepad_mapping:
                # print("unmapped code:", event.code)
                continue

            if (self.nav.is_homing or self.is_taking_photos) and event.code not in allowed_codes:
                continue

            self.process_event(event)

    def process_events_test(self):
        try:
            events = self.gamepad.read()
        except EOFError:
            events = []

        events = [e for e in events
                  if e.ev_type != 'Sync' and e.ev_type != 'Misc']

        codes = set([e.code for e in events
                     if e.code in self.settings.gamepad_mapping])

        for event in events[::-1]:
            for code in set(codes):
                if code == event.code:
                    self.process_event(event)
                    codes.remove(code)

            if len(codes) == 0:
                break

    def process_event(self, event):
        # print(event.ev_type, event.code, event.state)

        m = self.settings.gamepad_mapping.get(event.code, None)

        if m == 'position_test':  # temp
            if event.state == 1:
                self.nav.set_position(5000, 0, 0, 0)
            return

        fn_mapping = {
            'circular': self.move_circular,
            'camera': self.move_camera,
            'height_up': self.move_height_up,
            'height_down': self.move_height_down,
            'radial_forward': self.move_radially_forward,
            'radial_backward': self.move_radially_backward,
            'change_speed': self.change_speed,
            'homing': self.homing,
            'get_position': self.request_position,
            'stop': self.stop,
            'start_pause': self.start_pause
        }

        fn_mapping[m](event.state)

    def start_pause(self, state):
        if state == 0:
            return

        if self.nav.finished_homing is False:
            print("First you have to run 'homing'.")
            return

        if self.photographer is None:  # starting
            print("starting photographer")
            self.photographer = Photographer(self.settings, self.camera, self.nav)
            self.photographer.start()
            self.is_taking_photos = True
            return

        # pausing / continuing
        # Todo: account for pausing / continuing
        pass

    def stop(self, state):
        if state == 0:
            return

        if self.photographer is not None:
            self.photographer.stop = True
            self.is_taking_photos = False

            # this blocks the main thread, ie the program will not respond
            # while waiting; this is on purpose, I don't want to process any
            # gamepad events until I'm sure that the photographer is stopped
            self.photographer.join()
            self.photographer = None

        else:
            self.nav.stop()

    def homing(self, state):
        if state == 1:  # run homing when the button is pressed (not on release)
            self.nav.run_homing()

    def request_position(self, state):
        if state == 1:
            positions = self.nav.get_position()
            print('Positions (steps):', positions)
            positions = [self.settings.steps_to_physical(i, p)
                         for i, p in enumerate(positions)]
            print('Positions (physical):', [round(p, 3) for p in positions])

    def move_circular(self, state):
        s = self.settings.circular_settings
        stepper_idx = s['stepper_idx']

        min_val = s['gamepad_min_val']
        max_val = s['gamepad_max_val']
        zero_val_range = s['gamepad_zero_val_range']

        min_speed = s['stepper_min_speed']  # rpm
        max_speed = s['stepper_max_speed']
        min_speed_change = s['stepper_min_speed_delta']

        if state >= zero_val_range[0] and state <= zero_val_range[1]:
            state = (min_val + max_val) / 2

        v = (state - min_val) / (max_val - min_val)
        v = 2 * (v - 0.5)

        if abs(v) < 1e-6:
            if self._circ_speed == 0:
                return

            self.nav.set_velocity(stepper_idx, 0)
            self._circ_speed = 0
            return

        v_sign = +1 if v > 0 else -1
        v = min_speed + abs(v) * (max_speed - min_speed)
        v *= v_sign
        v = -v if s['flip_speed'] is True else v

        if abs(v - self._circ_speed) < min_speed_change:
            return

        self.nav.set_velocity(stepper_idx, v)
        self._circ_speed = v

    def move_camera(self, state):
        s = self.settings.camera_settings
        stepper_idx = s['stepper_idx']

        min_val = s['gamepad_min_val']
        max_val = s['gamepad_max_val']
        zero_val_range = s['gamepad_zero_val_range']

        min_speed = s['stepper_min_speed']  # rpm
        max_speed = s['stepper_max_speed']
        min_speed_change = s['stepper_min_speed_delta']

        if state >= zero_val_range[0] and state <= zero_val_range[1]:
            state = (min_val + max_val) / 2

        v = (state - min_val) / (max_val - min_val)
        v = 2 * (v - 0.5)

        if abs(v) < 1e-6:
            if self._cam_speed == 0:
                return

            self.nav.set_velocity(stepper_idx, 0)
            self._cam_speed = 0
            return

        v_sign = +1 if v > 0 else -1
        v = min_speed + abs(v) * (max_speed - min_speed)
        v *= v_sign
        v = -v if s['flip_speed'] is True else v

        if abs(v - self._cam_speed) < min_speed_change:
            return

        self.nav.set_velocity(stepper_idx, v)
        self._cam_speed = v

    def move_height_up(self, state):
        if self._height_down_speed != 0:  # can only go up or down at the same time
            return

        s = self.settings.height_settings
        stepper_idx = s['stepper_idx']

        if state == 0:  # button not pressed anymore
            self.nav.set_velocity(stepper_idx, 0)
            self._height_up_speed = 0
            return

        speed = s['stepper_default_speed']  # rpm
        speed = -speed if s['flip_speed'] is True else speed

        self.nav.set_velocity(stepper_idx, speed)
        self._height_up_speed = speed

    def move_height_down(self, state):
        if self._height_up_speed != 0:
            return

        s = self.settings.height_settings
        stepper_idx = s['stepper_idx']

        if state == 0:
            self.nav.set_velocity(stepper_idx, 0)
            self._height_down_speed = 0
            return

        speed = -s['stepper_default_speed']  # rpm
        speed = -speed if s['flip_speed'] is True else speed

        self.nav.set_velocity(stepper_idx, speed)
        self._height_down_speed = speed

    def move_radially_forward(self, state):
        if self._radial_backward_speed != 0:
            return

        s = self.settings.radial_settings
        stepper_idx = s['stepper_idx']

        if state == 0:
            self.nav.set_velocity(stepper_idx, 0)
            self._radial_forward_speed = 0
            return

        speed = s['stepper_default_speed']  # rpm
        speed = -speed if s['flip_speed'] is True else speed

        self.nav.set_velocity(stepper_idx, speed)
        self._radial_forward_speed = speed

    def move_radially_backward(self, state):
        if self._radial_forward_speed != 0:
            return

        s = self.settings.radial_settings
        stepper_idx = s['stepper_idx']

        if state == 0:
            self.nav.set_velocity(stepper_idx, 0)
            self._radial_backward_speed = 0
            return

        speed = -s['stepper_default_speed']  # rpm
        speed = -speed if s['flip_speed'] is True else speed

        self.nav.set_velocity(stepper_idx, speed)
        self._radial_backward_speed = speed

    def change_speed(self, state):
        if state == 0:
            return

        if self._radial_forward_speed != 0:
            s = self.settings.radial_settings

            dS = state * s['speed_delta']
            minS, maxS = s['stepper_min_speed'], s['stepper_max_speed']
            oldS = self._radial_forward_speed

            newS = 1 if oldS > 0 else -1
            newS = newS * max(min(abs(oldS) + dS, maxS), minS)

            if newS == oldS:
                return

            self.nav.set_velocity(s['stepper_idx'], newS)
            self._radial_forward_speed = newS

        elif self._radial_backward_speed != 0:
            s = self.settings.radial_settings

            dS = state * s['speed_delta']
            minS, maxS = s['stepper_min_speed'], s['stepper_max_speed']
            oldS = self._radial_backward_speed

            newS = 1 if oldS > 0 else -1
            newS = newS * max(min(abs(oldS) + dS, maxS), minS)

            if newS == oldS:
                return

            self.nav.set_velocity(s['stepper_idx'], newS)
            self._radial_backward_speed = newS

        elif self._height_up_speed != 0:
            s = self.settings.height_settings

            dS = state * s['speed_delta']
            minS, maxS = s['stepper_min_speed'], s['stepper_max_speed']
            oldS = self._height_up_speed

            newS = 1 if oldS > 0 else -1
            newS = newS * max(min(abs(oldS) + dS, maxS), minS)

            if newS == oldS:
                return

            self.nav.set_velocity(s['stepper_idx'], newS)
            self._height_up_speed = newS

        elif self._height_down_speed != 0:
            s = self.settings.height_settings

            dS = state * s['speed_delta']
            minS, maxS = s['stepper_min_speed'], s['stepper_max_speed']
            oldS = self._height_down_speed

            newS = 1 if oldS > 0 else -1
            newS = newS * max(min(abs(oldS) + dS, maxS), minS)

            if newS == oldS:
                return

            self.nav.set_velocity(s['stepper_idx'], newS)
            self._height_down_speed = newS
