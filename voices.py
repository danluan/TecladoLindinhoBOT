"""Yamaha PSR-E333 voice table (from the owner's manual) and its mapping to the GM soundfont.

Each voice: {"no": 1-497 as shown on the keyboard display, "msb", "lsb", "program" (0-127), "name", "category"}.
"""
import json
from pathlib import Path

VOICES: list[dict] = json.loads(Path(__file__).with_name("psr_e333_voices.json").read_text())
BY_NO = {v["no"]: v for v in VOICES}
_BY_BANK: dict[tuple[int, int, int], dict] = {}
for _v in VOICES:  # panel voices come first, so they win over XGlite duplicates
    _BY_BANK.setdefault((_v["msb"], _v["lsb"], _v["program"]), _v)

CATEGORY_PT = {
    "PIANO": "Piano", "E.PIANO": "Piano elétrico", "ORGAN": "Órgão", "ACCORDION": "Acordeão e gaita",
    "GUITAR": "Violão e guitarra", "BASS": "Baixo", "STRINGS": "Cordas", "CHOIR": "Coral",
    "SAXOPHONE": "Sax e madeiras", "TRUMPET": "Trompete e metais", "BRASS": "Naipe de metais",
    "FLUTE": "Flautas", "SYNTH": "Synth", "PERCUSSION": "Percussão", "WORLD": "Mundo e combinações",
    "SOUND EFFECTS": "Efeitos sonoros", "DRUM KITS": "Baterias e kits",
    "XG PIANO": "XG · Piano", "XG CHROMATIC": "XG · Percussão cromática", "XG ORGAN": "XG · Órgão",
    "XG GUITAR": "XG · Violão e guitarra", "XG BASS": "XG · Baixo", "XG STRINGS": "XG · Cordas",
    "XG ENSEMBLE": "XG · Conjuntos", "XG BRASS": "XG · Metais", "XG REED": "XG · Palhetas",
    "XG PIPE": "XG · Flautas", "XG SYNTH LEAD": "XG · Synth lead", "XG SYNTH PAD": "XG · Synth pad",
    "XG SYNTH EFFECTS": "XG · Synth efeitos", "XG WORLD": "XG · Mundo", "XG PERCUSSIVE": "XG · Percussivos",
    "XG SOUND EFFECTS": "XG · Efeitos sonoros",
}

DRUM_BANK = 128  # FluidR3_GM keeps its drum kits in bank 128
# Yamaha kit program -> closest FluidR3 kit (Dance Kit has no match; TR-808 is the nearest)
_KIT = {0: 0, 1: 1, 8: 8, 16: 16, 24: 24, 25: 25, 32: 32, 40: 40, 48: 48, 112: 25, 127: 0}
# Yamaha SFX voices (bank MSB 64) -> GM sound-effect programs, by keyword
_SFX = [
    (("thunder", "wind", "stream", "shower", "bubble", "feed"), 122),  # Seashore
    (("dog", "horse", "bird", "maou"), 123),  # Bird Tweet
    (("phone", "telephone"), 124),  # Telephone Ring
    (("car", "train", "jet", "starship", "submarine", "siren", "roller"), 125),  # Helicopter
    (("laugh", "scream", "footsteps", "heartbeat", "punch"), 126),  # Applause
    (("gun", "explosion", "firework", "burst"), 127),  # Gunshot
    (("noise", "slap", "click", "scratch", "door", "chime"), 120),  # Guitar Fret Noise
]


def lookup(msb: int, lsb: int, program: int) -> dict | None:
    """Keyboard voice for a bank/program the keyboard sent (or None if it isn't in the table)."""
    return _BY_BANK.get((msb, lsb, program)) or _BY_BANK.get((msb, 0, program))


def sound_for(voice: dict) -> tuple[int, int, bool]:
    """(soundfont bank, program, approximate?) that best reproduces a keyboard voice."""
    msb, prog = voice["msb"], voice["program"]
    if msb == 127:
        return DRUM_BANK, _KIT.get(prog, 0), prog not in _KIT or prog == 112
    if msb == 126 or voice["no"] == 122:  # SFX kits / Chinese percussion kit: no equivalent kit
        return DRUM_BANK, 0, True
    if msb == 64:
        name = voice["name"].lower()
        for words, gm in _SFX:
            if any(w in name for w in words):
                return 0, gm, True
        return 0, 127, True
    # bank MSB 0: XG variations (LSB != 0) are played with their GM base sound
    return 0, prog, voice["lsb"] not in (0, 112)


def gm_voice(program: int) -> dict:
    """Keyboard voice matching a plain GM program number (panel voice preferred)."""
    return lookup(0, 112, program) or lookup(0, 0, program) or {
        "no": 0, "msb": 0, "lsb": 0, "program": program, "name": f"GM {program}", "category": "XG PIANO"}


def public(voice: dict | None) -> dict | None:
    if not voice:
        return None
    return {**voice, "category_pt": CATEGORY_PT.get(voice["category"], voice["category"])}
