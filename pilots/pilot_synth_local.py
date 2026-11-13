"""Pilot 2: play the keyboard through FluidSynth on the local speakers (PipeWire)."""
import sys
import time

import mido

sys.path.insert(0, __file__.rsplit("/pilots/", 1)[0])
from common import find_midi_port, make_synth, route  # noqa: E402

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 30
synth, _ = make_synth()
synth.start(driver="pipewire")
port = mido.open_input(find_midi_port(), callback=lambda m: route(m, [synth]))
print(f"Tocando localmente por {secs:.0f}s — toque o teclado...")
time.sleep(secs)
port.close()
synth.delete()
