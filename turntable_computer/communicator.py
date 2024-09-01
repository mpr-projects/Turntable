import threading
import queue
import time


STATUS_INTERVAL = 2 + 0.2  # +0.2 to allow for timing issues and communication overheads



class Communicator(threading.Thread):
    def __init__(self, serial, q_send, q_receive):
        super().__init__()
        self.serial = serial
        self.q_send = q_send
        self.q_receive = q_receive

        self.is_initialized = False
        self.status_counter = 0  # uint8_t on Arduino --> value range [0, 255]
        self.previous_status_time = None  # 2 seconds should pass between updates

        self.stop = False  # simple code, don't need threading.Event here

    def run(self):
        while True :
            time.sleep(0.01)

            # check for stopping
            if self.stop is True:
                break

            # receive commands from the main thread and pass them on to the Arduino
            try:
                msg = self.q_receive.get(block=False)
                self.serial.write(msg)

                if msg == 'I'.encode('utf-8') and self.is_initialized is False:
                    print("Starting Initialization")
                    msg_ = self.serial.readline()
                    cmd, idx = msg_[:1].decode().strip(), msg_[1]
                    
                    if not (cmd == 'S' and idx == 0):
                        self.q_send.put("Initialization Error")
                        print(f"Error: Expected reply 'S0' but got {msg_}.")
                        break

                    print("Received Reply")
                    self.is_initialized = True
                    self.status_counter = 1
                    self.previous_status_time = time.time()
                    self.q_send.put("Initialization Successful")

            except queue.Empty:
                pass

            if self.is_initialized is True:
                t = time.time()

                # deal with status messages from Arduino
                if self.serial.in_waiting > 0:
                    msg = self.serial.readline()
                    cmd, data = msg[:1].decode('utf-8').strip(), msg[1:]
                    # print('received:', cmd, data)

                    if cmd == 'S' :
                        idx = data[0]

                        if idx != self.status_counter:
                            print(f"Error: Expected counter value {self.status_counter} but got {idx}.")
                            break

                        self.status_counter = (self.status_counter + 1) % 256  # accounting for uint8_t of status counter
                        self.previous_status_time = t

                    elif cmd == 'Z':  # returning current position
                        data = int.from_bytes(data.strip(), byteorder='little', signed=True)
                        self.q_send.put(data)

                    else:
                        if cmd != '_':  # _ is comment
                            self.q_send.put(cmd)
                        else:
                            print(' ', data)  # .decode().strip())

                # check that Arduino is (still) sending status updates on time
                t_gap = t - self.previous_status_time

                if t_gap > STATUS_INTERVAL:
                    print(f"Error: Arduino missed status update, time passed is {t_gap}.")
                    break

            else:
                if self.serial.in_waiting > 0:
                    # the Arduino is sending messages even though initialization
                    # hasn't happened --> we restarted the program on the RPi
                    # but the Arduino kept running; two options: i) reset the
                    # Arduino and ii) assume that it was set up correctly and
                    # may even be homed (could ask the Arduino if it has run
                    # homing); for now I just reset it, that may change ...
                    self.serial.write('R'.encode('utf-8'))

                    time.sleep(0.5)  # give the Arduino time to reset and reply
                    reset_successful = False

                    while self.serial.in_waiting > 0:
                        msg = self.serial.readline().decode('utf-8').strip()

                        if msg == 'R':
                            print("Arduino has been reset.")
                            reset_successful = True

                    if reset_successful is False:
                        print("Error when resetting Arduino.")
                        break

        print(" Exiting Communicator")
