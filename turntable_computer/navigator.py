import serial
import queue
import time
import struct

from communicator import Communicator


class Navigator:
    def __init__(self, port, baud_rate):
        self.get_serial(port, baud_rate)  # Todo: should this be done in Communicator?
        self.q_send = queue.Queue()
        self.q_receive = queue.Queue()

        self.com = Communicator(self.serial, self.q_receive, self.q_send)
        self.com.start()

    def initialize(self):
        self.q_send.put("I".encode('utf-8'))
        res = self.q_receive.get()

        if res == 'Initialization Error':
            raise RuntimeError("Arduino Initialization Error")
        # else res == 'Initialization Successful', nothing to do

    def shutdown(self):
        self.com.stop = True
        self.com.join()

    def set_velocity(self, v):
        self.clear_q_receive()  # Todo: should check for important messages in queue!!

        c0 = bytearray.fromhex('56')  # V
        c1 = bytearray(struct.pack("f", v))
        self.q_send.put(c0 + c1)

        res = self.q_receive.get()

        if res != 'A':
            raise RuntimeError(f"Error when setting velocity to {v}.", res)

    def set_position(self, p, v):
        self.clear_q_receive()  # Todo: should check for important messages in queue!!
        c0 = bytearray.fromhex('50')  # P
        c1 = bytearray(p.to_bytes(4, byteorder='little', signed=True))
        c2 = bytearray(struct.pack("f", v))
        self.q_send.put(c0 + c1 + c2)

        # print("waiting for position acknowledge")
        res = self.q_receive.get()

        if res != 'A':
            raise RuntimeError(f"Error when setting positions {p}.")

    def get_position(self):
        self.clear_q_receive()  # Todo: should check for important messages in queue!!
        self.q_send.put('Z'.encode('utf-8'))
        return self.q_receive.get()

    def stop(self):
        self.clear_q_receive()  # Todo: should check for important messages in queue!!

        self.q_send.put('Y'.encode('utf-8'))

        res = self.q_receive.get()

        if res != 'A':
            raise RuntimeError(f"Error when stopping.")

    def get_serial(self, port, baud_rate):
        while True:
            try:
                self.serial = serial.Serial(port, baud_rate)
                return
            except serial.serialutil.SerialException:
                pass

    def clear_q_receive(self):
        with self.q_receive.mutex:
            self.q_receive.queue.clear()
