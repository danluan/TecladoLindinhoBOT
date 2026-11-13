"""Discord bot that plays a MIDI keyboard live into a voice channel via FluidSynth."""
import asyncio
import logging
import os

import discord
import mido
import numpy as np
from discord import app_commands
from dotenv import load_dotenv

import voices
from common import FRAME_SAMPLES, find_midi_port, make_synth

load_dotenv()
log = logging.getLogger("midibot")


class Engine:
    """Synth(s) plus the sound settings shared by slash commands and the web panel."""

    def __init__(self):
        # keyboard voice per MIDI channel: 0 = main voice, 1 = dual (layer) voice
        self.voice: dict = voices.BY_NO.get(int(os.environ.get("VOICE", "88")), voices.BY_NO[1])
        self.dual_voice: dict | None = None
        self.follow_keyboard = os.environ.get("FOLLOW_KEYBOARD", "1") == "1"
        self.volume = 1.0
        self.reverb = 0.3
        self.level = 0.0  # last output peak, 0..1, for the panel meter
        self.synth, self.sfid = make_synth(gain=0.8)
        self.synths = [(self.synth, self.sfid)]
        if os.environ.get("LOCAL_MONITOR") == "1":  # also hear it on this PC, with no Discord delay
            local, local_sfid = make_synth(gain=0.8)
            local.start(driver="pipewire")
            self.synths.append((local, local_sfid))
        self.set_voice(self.voice)
        self.set_reverb(self.reverb)

    def all_synths(self):
        return [s for s, _ in self.synths]

    def sound_name(self, voice: dict | None) -> str | None:
        """Name of the soundfont preset actually playing a keyboard voice."""
        if not voice:
            return None
        bank, prog, _ = voices.sound_for(voice)
        return self.synth.sfpreset_name(self.sfid, bank, prog)

    def set_voice(self, voice: dict, channel: int = 0):
        """Play a PSR-E333 voice on a channel using the closest soundfont preset."""
        if channel == 0:
            self.voice = voice
        elif channel == 1:
            self.dual_voice = voice
        bank, prog, _ = voices.sound_for(voice)
        for s, sfid in self.synths:
            s.program_select(channel, sfid, bank, prog)

    def set_reverb(self, amount: float):
        self.reverb = max(0.0, min(1.0, amount))
        for s in self.all_synths():
            s.set_reverb(roomsize=0.2 + 0.7 * self.reverb, damping=0.4, width=0.9, level=self.reverb)

    def panic(self):
        for s in self.all_synths():
            for ch in range(16):
                s.cc(ch, 123, 0)  # All Notes Off
                s.cc(ch, 64, 0)  # release sustain pedal

    async def demo(self):
        for n in (60, 64, 67, 72, 67, 64, 60):
            for s in self.all_synths():
                s.noteon(0, n, 100)
            await asyncio.sleep(0.25)
            for s in self.all_synths():
                s.noteoff(0, n)


engine = Engine()


class MidiSynthSource(discord.AudioSource):
    """Pulls 20 ms of PCM from FluidSynth each time discord.py's player asks for a frame."""

    def read(self) -> bytes:
        pcm = np.clip(engine.synth.get_samples(FRAME_SAMPLES), -32768, 32767).astype(np.int16)
        engine.level = max(int(np.abs(pcm).max()) / 32768, engine.level * 0.85)
        return pcm.tobytes()

    def is_opus(self) -> bool:
        return False


class MidiInput:
    """Keeps the keyboard port open, reopening it if it's unplugged and plugged back."""

    def __init__(self):
        self.port = None
        self.out = None  # keyboard's MIDI in, used to change its voice from the panel
        self.notes = 0
        self.bank = {}  # channel -> [MSB, LSB] from the CC0/CC32 sent right before a program change

    def _on_msg(self, msg):
        """Mirror the keyboard on its own MIDI channels (0 = main voice, 1 = dual/layer voice)."""
        synths = engine.all_synths()
        if msg.type == "note_on" and msg.velocity:
            self.notes += 1
            for s in synths:
                s.noteon(msg.channel, msg.note, msg.velocity)
        elif msg.type in ("note_on", "note_off"):
            for s in synths:
                s.noteoff(msg.channel, msg.note)
        elif msg.type == "program_change":
            msb, lsb = self.bank.get(msg.channel, (0, 0))
            voice = voices.lookup(msb, lsb, msg.program) or voices.gm_voice(msg.program)
            if engine.follow_keyboard and msg.channel in (0, 1):
                engine.set_voice(voice, msg.channel)
                log.info("Teclado: canal %d → voz %03d %s", msg.channel, voice["no"], voice["name"])
        elif msg.type == "control_change":
            if msg.control in (0, 32):  # bank select: remembered and resolved on the program change
                self.bank.setdefault(msg.channel, [0, 0])[msg.control == 32] = msg.value
                return
            if msg.control in (7, 91) and not engine.follow_keyboard:  # voice volume / reverb
                return
            for s in synths:
                s.cc(msg.channel, msg.control, msg.value)
        elif msg.type == "pitchwheel":
            for s in synths:
                s.pitch_bend(msg.channel, msg.pitch)

    def send_voice(self, voice: dict):
        """Make the keyboard itself switch to this exact voice (bank MSB/LSB + program)."""
        if not self.out:
            return
        try:
            self.out.send(mido.Message("control_change", channel=0, control=0, value=voice["msb"]))
            self.out.send(mido.Message("control_change", channel=0, control=32, value=voice["lsb"]))
            self.out.send(mido.Message("program_change", channel=0, program=voice["program"]))
        except Exception:
            log.exception("Falha ao mandar a voz para o teclado")

    async def watch(self):
        while True:
            try:
                name = find_midi_port()
            except RuntimeError:
                name = None
            if self.port and (name is None or name != self.port.name):
                log.warning("Teclado desconectado")
                self.port.close()
                self.port = None
                if self.out:
                    self.out.close()
                    self.out = None
                engine.panic()
            if not self.port and name:
                self.port = mido.open_input(name, callback=self._on_msg)
                if name in mido.get_output_names():
                    self.out = mido.open_output(name)
                    if engine.follow_keyboard:  # start with the keyboard on the bot's voice
                        self.send_voice(engine.voice)
                log.info("Teclado conectado: %s (saída para o teclado: %s)", name, bool(self.out))
            await asyncio.sleep(2)


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.midi = MidiInput()

    @property
    def vc(self) -> discord.VoiceClient | None:
        return self.voice_clients[0] if self.voice_clients else None

    async def join(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        vc = channel.guild.voice_client
        if vc:
            await vc.move_to(channel)
        else:
            vc = await channel.connect(self_deaf=True)
        if not vc.is_playing():
            vc.play(
                discord.PCMVolumeTransformer(MidiSynthSource(), volume=engine.volume),
                after=lambda e: e and log.error("player parou com erro: %r", e),
            )
        log.info("Tocando em %s / %s", channel.guild.name, channel.name)
        return vc

    async def leave(self):
        for vc in list(self.voice_clients):
            await vc.disconnect()

    def set_volume(self, volume: float):
        engine.volume = max(0.0, min(2.0, volume))
        for vc in self.voice_clients:
            if isinstance(vc.source, discord.PCMVolumeTransformer):
                vc.source.volume = engine.volume

    def dave_ready(self) -> bool | None:
        vc = self.vc
        if not vc:
            return None
        c = vc._connection
        return c.dave_protocol_version == 0 or c.can_encrypt

    async def watch_dave(self):
        """Warn when a DAVE (E2EE) call isn't encrypting: listeners would silently drop our audio."""
        last = None
        while True:
            state = self.dave_ready()
            if state != last and state is not None:
                (log.info if state else log.warning)("Criptografia de voz pronta: %s", state)
            last = state
            await asyncio.sleep(2)

    async def setup_hook(self):
        from panel import start_panel

        self.loop.create_task(self.midi.watch())
        self.loop.create_task(self.watch_dave())
        await start_panel(self, engine)
        guild_id = os.environ.get("GUILD_ID")
        if guild_id:  # guild sync is instant; global sync can take a while
            guild = discord.Object(int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = Bot()


@bot.event
async def on_ready():
    log.info("Logado como %s", bot.user)


@bot.tree.command(name="entrar", description="Entra na sua call e começa a tocar o teclado")
async def entrar(inter: discord.Interaction):
    voice = getattr(inter.user, "voice", None)
    if not voice or not voice.channel:
        return await inter.response.send_message("Entre numa call primeiro.", ephemeral=True)
    await bot.join(voice.channel)
    await inter.response.send_message(f"🎹 Tocando em **{voice.channel.name}**")


@bot.tree.command(name="sair", description="Sai da call")
async def sair(inter: discord.Interaction):
    if not inter.guild.voice_client:
        return await inter.response.send_message("Não estou em call.", ephemeral=True)
    await inter.guild.voice_client.disconnect()
    await inter.response.send_message("👋 Saí da call")


@bot.tree.command(name="instrumento", description="Troca a voz (número do PSR-E333, 1–497)")
@app_commands.describe(voz="Número da voz no teclado, ou digite o nome para buscar")
async def instrumento(inter: discord.Interaction, voz: app_commands.Range[int, 1, 497]):
    voice = voices.BY_NO[voz]
    engine.set_voice(voice)
    if engine.follow_keyboard:
        bot.midi.send_voice(voice)
    await inter.response.send_message(f"🎼 Voz {voice['no']:03d} — {voice['name']}")


@instrumento.autocomplete("voz")
async def instrumento_autocomplete(inter: discord.Interaction, current: str):
    q = current.strip().lower()
    hits = [v for v in voices.VOICES if not q or q in v["name"].lower() or str(v["no"]).startswith(q)]
    return [app_commands.Choice(name=f"{v['no']:03d} {v['name']}", value=v["no"]) for v in hits[:25]]


@bot.tree.command(name="volume", description="Volume na call (0–200%)")
async def volume(inter: discord.Interaction, porcentagem: app_commands.Range[int, 0, 200]):
    bot.set_volume(porcentagem / 100)
    await inter.response.send_message(f"🔊 Volume {porcentagem}%")


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Defina DISCORD_TOKEN no arquivo .env")
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (logging.StreamHandler(), logging.FileHandler("bot.log", mode="w")):
        h.setFormatter(fmt)
        root.addHandler(h)
    bot.run(token, log_handler=None)
