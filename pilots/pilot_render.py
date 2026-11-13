"""Pilot 3: render audio the same way the bot does (get_samples per 20 ms) into a WAV.

With --demo, plays a C major arpeggio instead of reading the keyboard (no human needed).
"""
import sys
import time
import wave

import mido
import numpy as np

sys.path.insert(0, __file__.rsplit("/pilots/", 1)[0])
from common import FRAME_SAMPLES, SAMPLE_RATE, find_midi_port, make_synth, route  # noqa: E402

demo = "--demo" in sys.argv
out_path = "out.wav"
secs = 5
synth, _ = make_synth()

port = None
if demo:
    script = [(i * 0.4, 60 + n) for i, n in enumerate([0, 4, 7, 12, 7, 4, 0])]
else:
    port = mido.open_input(find_midi_port(), callback=lambda m: route(m, [synth]))
    print(f"Gravando {secs}s — toque o teclado...")

frames = []
start = time.monotonic()
for i in range(secs * 50):
    t = i * 0.02
    if demo:
        for at, note in script:
            if abs(at - t) < 0.01:
                synth.noteon(0, note, 100)
            if abs(at + 0.35 - t) < 0.01:
                synth.noteoff(0, note)
    pcm = synth.get_samples(FRAME_SAMPLES)  # interleaved int16 stereo
    frames.append(np.clip(pcm, -32768, 32767).astype(np.int16).tobytes())
    # pace like Discord's player does
    delay = start + (i + 1) * 0.02 - time.monotonic()
    if delay > 0 and not demo:
        time.sleep(delay)

if port:
    port.close()
data = b"".join(frames)
assert len(frames[0]) == 3840, f"frame com {len(frames[0])} bytes, esperado 3840"
with wave.open(out_path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SAMPLE_RATE)
    w.writeframes(data)
peak = np.abs(np.frombuffer(data, dtype=np.int16)).max()
print(f"{out_path}: {len(data)} bytes, pico {peak} ({'tem som' if peak > 100 else 'SILÊNCIO'})")
