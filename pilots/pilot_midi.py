"""Pilot 1: print MIDI messages from the keyboard for N seconds."""
import sys
import time

import mido

sys.path.insert(0, __file__.rsplit("/pilots/", 1)[0])
from common import find_midi_port  # noqa: E402

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 15
print("Portas MIDI:", mido.get_input_names())
port_name = find_midi_port()
print(f"Lendo '{port_name}' por {secs:.0f}s — toque o teclado...")
count = 0
with mido.open_input(port_name) as port:
    end = time.monotonic() + secs
    while time.monotonic() < end:
        for msg in port.iter_pending():
            if msg.type in ("clock", "active_sensing"):
                continue
            count += 1
            print(msg)
        time.sleep(0.005)
print(f"{count} mensagens recebidas")
