"""Shared pieces: soundfont lookup, MIDI port lookup, synth setup and MIDI routing."""
import glob
import os

import fluidsynth
import mido

SAMPLE_RATE = 48000
FRAME_SAMPLES = 960  # 20 ms at 48 kHz, what Discord expects per packet

SOUNDFONT_CANDIDATES = [
    os.environ.get("SOUNDFONT", ""),
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/soundfonts/default.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",  # Debian/Ubuntu (fluid-soundfont-gm)
    *glob.glob("/usr/share/soundfonts/*.sf[23]"),
    *glob.glob("/usr/share/sounds/sf[23]/*.sf[23]"),
    *glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.sf[23]")),
]


def find_soundfont() -> str:
    for path in SOUNDFONT_CANDIDATES:
        if path and os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "Nenhum soundfont encontrado. Rode: sudo pacman -S soundfont-fluid "
        "(ou defina SOUNDFONT=/caminho/arquivo.sf2)"
    )


def find_midi_port(hint: str | None = None) -> str:
    hint = (hint or os.environ.get("MIDI_PORT", "DigitalKBD")).lower()
    names = mido.get_input_names()
    for name in names:
        if hint in name.lower():
            return name
    raise RuntimeError(f"Porta MIDI com '{hint}' não encontrada. Disponíveis: {names}")


def make_synth(gain: float = 0.6, program: int | None = None) -> tuple[fluidsynth.Synth, int]:
    if program is None:
        program = int(os.environ.get("INSTRUMENT", "0"))
    synth = fluidsynth.Synth(gain=gain, samplerate=float(SAMPLE_RATE))
    sfid = synth.sfload(find_soundfont())
    synth.program_select(0, sfid, 0, program)  # channel 0, bank 0, GM program (0=piano, 79=ocarina)
    return synth, sfid


def route(msg: mido.Message, synths) -> None:
    """Forward one MIDI message to every synth (all on channel 0 regardless of input channel)."""
    for s in synths:
        if msg.type == "note_on" and msg.velocity > 0:
            s.noteon(0, msg.note, msg.velocity)
        elif msg.type in ("note_off", "note_on"):
            s.noteoff(0, msg.note)
        elif msg.type == "control_change":
            s.cc(0, msg.control, msg.value)
        elif msg.type == "pitchwheel":
            s.pitch_bend(0, msg.pitch)
