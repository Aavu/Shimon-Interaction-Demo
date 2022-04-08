"""
Author: Raghavasimhan Sankaranarayanan
Date: 04/08/2022
"""

import rtmidi
import pretty_midi
import pyaudio
from rtmidi.midiconstants import NOTE_OFF, NOTE_ON
from audioToMidi import AudioMidiConverter
from audioDevice import AudioDevice
from tempoTracker import TempoTracker
import numpy as np
from threading import Thread, Lock
import time


class QnADemo:
    def __init__(self, raga_map, sr=16000, frame_size=256, activation_threshold=0.02, n_wait=16,
                 input_dev_name='Line 6 HX Stomp', outlier_filter_coeff=2):
        self.active = False

        self.activation_threshold = activation_threshold
        self.n_wait = n_wait
        self.wait_count = 0
        self.playing = False
        self.phrase = []

        self.process_thread = Thread()
        self.lock = Lock()

        self.midi_out = rtmidi.MidiOut()
        self.midi_out.open_virtual_port("My virtual output")

        self.audioDevice = AudioDevice(self.callback_fn, rate=sr, frame_size=frame_size, input_dev_name=input_dev_name,
                                       channels=4)
        self.audio2midi = AudioMidiConverter(raga_map=raga_map, sr=sr, frame_size=frame_size,
                                             outlier_coeff=outlier_filter_coeff)
        self.audioDevice.start()

    def reset_var(self):
        self.wait_count = 0
        self.playing = False
        self.phrase = []

    def callback_fn(self, in_data: bytes, frame_count: int, time_info: dict[str, float], status: int) -> tuple[
        bytes, int]:
        if not self.active:
            self.reset_var()
            return in_data, pyaudio.paContinue

        y = np.frombuffer(in_data, dtype=np.int16)
        y = y[::2][1::2]  # Get all the even indices then get all odd indices for ch-3 of HX Stomp
        y = self.int16_to_float(y)
        activation = np.abs(y).mean()
        # print(activation, self.activation_threshold)
        if activation > self.activation_threshold:
            print(activation)
            self.playing = True
            self.wait_count = 0
            self.lock.acquire()
            self.phrase.append(y)
            self.lock.release()
            # print("Capturing...")
        else:
            if self.wait_count > self.n_wait:
                self.playing = False
                self.wait_count = 0
                # print("Silence buffer...")
            else:
                self.lock.acquire()
                if self.playing:
                    self.phrase.append(y)
                self.lock.release()
                self.wait_count += 1
        return in_data, pyaudio.paContinue

    def reset(self):
        self.stop()
        self.audioDevice.reset()
        self.midi_out.close_port()

    @staticmethod
    def int16_to_float(x):
        return x / (1 << 15)

    @staticmethod
    def to_float(x):
        if x.dtype == 'float32':
            return x
        elif x.dtype == 'uint8':
            return (x / 128.) - 1
        else:
            bits = x.dtype.itemsize * 8
            return x / (2 ** (bits - 1))

    def start(self):
        self.reset_var()
        if self.process_thread.is_alive():
            self.process_thread.join()
        self.lock.acquire()
        self.active = True
        self.lock.release()
        self.process_thread = Thread(target=self._process)
        self.process_thread.start()

    def _process(self):
        while True:
            time.sleep(0.1)
            self.lock.acquire()
            if not self.active:
                self.lock.release()
                return

            if not (self.playing or len(self.phrase) == 0):
                self.lock.release()
                break
            self.lock.release()

        self.lock.acquire()
        phrase = np.hstack(self.phrase)
        self.phrase = []
        self.lock.release()

        if len(phrase) > 0:
            notes, duration = self.audio2midi.convert(phrase, return_duration=True)
            print("notes:", notes)  # Send to shimon
            print("duration:", duration)
            self.perform(notes, duration)

        self._process()

    def stop(self):
        self.lock.acquire()
        self.active = False
        self.lock.release()
        if self.process_thread.is_alive():
            self.process_thread.join()

    def perform(self, notes, duration):
        time.sleep(0.5)     # Shimon hardware wait simulation
        for _i in range(len(notes)):
            self.lock.acquire()
            if not self.active:
                self.lock.release()
                break
            self.lock.release()

            note_on = [NOTE_ON, notes[_i], 80]
            note_off = [NOTE_OFF, notes[_i], 0]
            self.midi_out.send_message(note_on)
            time.sleep(duration[_i])
            self.midi_out.send_message(note_off)


class BeatDetectionDemo:
    def __init__(self, smoothing=4):
        self.tempo_tracker = TempoTracker(smoothing=smoothing)

    def start(self):
        self.tempo_tracker.start()

    def stop(self):
        self.tempo_tracker.stop()

    def update_tempo(self, msg, dt):
        if msg[0] == NOTE_ON:
            tempo = self.tempo_tracker.track_tempo(msg, dt)
            if tempo:
                print(tempo)

    def get_tempo(self):
        return self.tempo_tracker.tempo


class SongDemo:
    def __init__(self, midi_file: str):
        self.midi_out = rtmidi.MidiOut()
        self.midi_out.open_virtual_port("Song Demo Port")

        self.notes, self.onsets, self.file_tempo = self._parse_midi(midi_file)
        self.tempo = self.file_tempo
        self.playing = False
        self.thread = Thread()
        self.lock = Lock()

    def __del__(self):
        self.reset()

    def set_tempo(self, tempo):
        self.tempo = tempo

    def start(self):
        self.playing = True
        self.thread = Thread(target=self.perform)
        self.thread.start()

    def stop(self):
        self.lock.acquire()
        self.playing = False
        self.lock.release()
        self.wait()

    def perform(self):
        m = self.file_tempo / self.tempo
        i = 0
        while i < len(self.notes):
            poly_notes = []
            while i < len(self.onsets):
                if len(poly_notes) > 0 and poly_notes[-1] == self.onsets[i]:
                    poly_notes.append(self.notes[i])
                    i += 1
                elif i < len(self.notes) - 1 and self.onsets[i] == self.onsets[i+1]:
                    poly_notes.append(self.notes[i])
                    poly_notes.append(self.notes[i+1])
                    i += 2
                else:
                    break

            self.lock.acquire()
            if not self.playing:
                self.lock.release()
                return
            self.lock.release()

            duration = 0
            if len(poly_notes) > 0:
                if i < len(self.notes):
                    duration = self.notes[i].start - poly_notes[0].start
                for j in range(len(poly_notes)):
                    note_on = [NOTE_ON, poly_notes[j].pitch, poly_notes[j].velocity]
                    note_off = [NOTE_OFF, poly_notes[j].pitch, 0]
                    self.midi_out.send_message(note_on)
                    self.midi_out.send_message(note_off)
            else:
                if i < len(self.notes) - 1:
                    duration = self.notes[i+1].start - self.notes[i].start
                note_on = [NOTE_ON, self.notes[i].pitch, self.notes[i].velocity]
                note_off = [NOTE_OFF, self.notes[i].pitch, 0]
                self.midi_out.send_message(note_on)
                self.midi_out.send_message(note_off)
                i += 1

            time.sleep(duration * m)

    def wait(self):
        if self.thread.is_alive():
            self.thread.join()

    @staticmethod
    def _parse_midi(midi_file):
        midi_data = pretty_midi.PrettyMIDI(midi_file)
        onsets = []
        for o in midi_data.instruments[0].get_onsets():
            onsets.append(midi_data.time_to_tick(o))

        file_tempo = round(midi_data.get_tempo_changes()[1][0], 3)
        return midi_data.instruments[0].notes, onsets, file_tempo

    def reset(self):
        self.stop()
        self.midi_out.close_port()


