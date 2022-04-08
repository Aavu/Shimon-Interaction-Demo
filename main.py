"""
Author: Raghavasimhan Sankaranarayanan
Date: 04/08/2022
"""

import enum
from rtmidi.midiconstants import CONTROL_CHANGE
import time
from midiDevice import MidiDevice
from demos import BeatDetectionDemo, QnADemo, SongDemo
import signal

ctrl_device = None
keys = None
qna_demo = None
beat_detection_demo = None
song_demo = None


def sig_handle():
    if qna_demo:
        qna_demo.reset()
    if ctrl_device:
        ctrl_device.reset()
    if keys:
        keys.reset()
    if song_demo:
        song_demo.stop()


class Demo(enum.IntEnum):
    InActive = 0
    Violin = 1
    Keys = 2
    Song = 3


# user_data = {'bd_demo': beat_detection_demo, 'qa_demo': qna_demo, 'song_demo': song_demo, 'running': running, 'demo': current_demo}
def ctrl_callback(msg, dt, user_data):
    print(msg)
    if msg[0] == CONTROL_CHANGE:
        _, cc, val = msg
        if cc == 10:
            if val == Demo.InActive:
                user_data['running'][0] = False
                return
            if user_data['demo'][0] != val:
                user_data['demo'][0] = Demo(val)
                manage_demos(val, user_data['bd_demo'], user_data['qa_demo'], user_data['song_demo'])


# user_data = {'bd_demo': beat_detection_demo, 'demo': current_demo}
def keys_callback(msg, dt, user_data):
    _bd_demo = user_data['bd_demo']
    if _bd_demo and user_data['demo'][0] == Demo.Keys:
        _bd_demo.update_tempo(msg, dt)


def manage_demos(val, bd_demo: BeatDetectionDemo, qa_demo: QnADemo, song_demo: SongDemo):
    if val == Demo.Keys:
        print("Beat Detection Demo")
        song_demo.stop()
        qa_demo.stop()
        bd_demo.start()

    elif val == Demo.Violin:
        print("Q & A Demo")
        song_demo.stop()
        bd_demo.stop()
        qa_demo.start()

    elif val == Demo.Song:
        print("Song Demo")
        bd_demo.stop()
        qa_demo.stop()
        tempo = bd_demo.get_tempo()
        if tempo and tempo > 0:
            song_demo.set_tempo(tempo)
        song_demo.start()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sig_handle)

    SONG_MIDI_FILE = 'assets/shimons_morning.mid'

    # need to use list to pass the value by reference
    current_demo = [Demo.InActive]
    running = [True]

    beat_detection_demo = BeatDetectionDemo(smoothing=4)
    kapi_map = [0, 2, 2, 3, 4, 5, 5, 7, 8, 9, 10, 11]
    audio_interface = 'Line 6 HX Stomp'     # 'Universal Audio Thunderbolt'
    qna_demo = QnADemo(kapi_map, sr=16000, frame_size=256, activation_threshold=0.01, n_wait=32,
                       input_dev_name=audio_interface, outlier_filter_coeff=2)
    song_demo = SongDemo(SONG_MIDI_FILE)


    # MidiDevice.list_input_devices()
    ctrl_device = MidiDevice('HX Stomp', callback_fn=ctrl_callback,
                             user_data={'bd_demo': beat_detection_demo, 'qa_demo': qna_demo, 'song_demo': song_demo, 'running': running,
                                        'demo': current_demo})
    keys = MidiDevice('iRig KEYS 37', callback_fn=keys_callback, user_data={'bd_demo': beat_detection_demo, 'demo': current_demo})

    while running[0]:
        time.sleep(.1)

    # for i in range(200):
    #     time.sleep(.1)
    #     if not running[0]:
    #         break

    qna_demo.reset()
    ctrl_device.reset()
    keys.reset()
    song_demo.reset()
