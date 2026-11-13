"""Pilot 4: join a voice channel and play a 440 Hz sine for 5 s (no MIDI involved).

Usage: uv run pilots/pilot_voice.py <voice_channel_id>
"""
import asyncio
import math
import os
import sys

import discord
import numpy as np
from dotenv import load_dotenv

load_dotenv()
CHANNEL_ID = int(sys.argv[1])


class Sine(discord.AudioSource):
    def __init__(self, freq=440.0, secs=5.0):
        self.n = 0
        self.total = int(secs * 50)
        t = np.arange(960) / 48000
        self.freq = freq

    def read(self) -> bytes:
        if self.n >= self.total:
            return b""
        t = (np.arange(960) + self.n * 960) / 48000
        s = (0.3 * 32767 * np.sin(2 * math.pi * self.freq * t)).astype(np.int16)
        self.n += 1
        return np.repeat(s, 2).tobytes()  # stereo interleaved

    def is_opus(self):
        return False


client = discord.Client(intents=discord.Intents.default())


@client.event
async def on_ready():
    print("Logado como", client.user)
    channel = client.get_channel(CHANNEL_ID) or await client.fetch_channel(CHANNEL_ID)
    vc = await channel.connect()
    print("Conectado em", channel.name, "- tocando 440 Hz")
    done = asyncio.Event()
    vc.play(Sine(), after=lambda e: client.loop.call_soon_threadsafe(done.set))
    await done.wait()
    await vc.disconnect()
    print("OK: senoide enviada")
    await client.close()


client.run(os.environ["DISCORD_TOKEN"])
