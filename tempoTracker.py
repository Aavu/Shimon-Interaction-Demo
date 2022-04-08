import time
import numpy as np


class TempoTracker:
    def __init__(self, smoothing=5, timeout_sec=5):
        self.smoothing = smoothing
        self.timeout = timeout_sec
        self.history = None
        self.idx = 0
        self.tempo = None
        self.num_out = 0
        self.last_time = time.time()
        self.first_time = True
        self.active = False
        self.reset_vars()

    def track_tempo(self, note_on_msg, dt):
        if not self.active:
            self.reset_vars()
            return None

        if self.first_time:
            self.last_time = time.time()
            self.first_time = False

        new_time = time.time() - self.last_time
        if new_time < 50e-3:
            return None
        elif new_time > self.timeout:
            self.reset_vars()
            return None

        self.last_time = time.time()
        self.history[self.idx] = new_time

        self.idx = (self.idx + 1) % len(self.history)
        if self.num_out > 3:
            t = self.history.mean()
            self.tempo = 60/t
            # print(np.round(self.tempo))
        self.num_out += 1

        return self.tempo

    def reset_vars(self):
        self.history = np.zeros(self.smoothing, dtype=float)
        self.idx = 0
        self.num_out = 0
        self.last_time = time.time()
        self.first_time = True

    def start(self):
        self.active = True

    def stop(self):
        self.active = False
