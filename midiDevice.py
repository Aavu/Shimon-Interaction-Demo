"""
Author: Raghavasimhan Sankaranarayanan
Date: 04/08/2022
"""

import rtmidi
from rtmidi import midiutil


class MidiDevice:
    def __init__(self, name, callback_fn=None, user_data=None):
        self.initialized = False
        self.midi_in = rtmidi.MidiIn(queue_size_limit=1024)
        self.input = None
        self.name = name
        self.callback_fn = callback_fn
        self.user_data = user_data
        if self.name in self.midi_in.get_ports():
            self.input, _ = midiutil.open_midiinput(self.name)
            self.input.ignore_types()
            print(f"Using MIDI Device: {self.name}")

            self.input.set_callback(self.callback, self)
            self.initialized = True
        else:
            print("Warning: MIDI device not found")

    @staticmethod
    def list_input_devices():
        print(rtmidi.MidiIn().get_ports())

    def reset(self):
        if self.input:
            self.input.close_port()
            self.input.delete()

    def set_callback(self, callback_fn):
        self.callback_fn = callback_fn

    @staticmethod
    def callback(msg, dev):
        dev.callback_fn(msg[0], msg[1], dev.user_data)
