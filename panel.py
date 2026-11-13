"""Local web control panel (aiohttp, ships with discord.py). Bound to localhost only."""
import logging
import os
from pathlib import Path

import discord
from aiohttp import web

import voices

log = logging.getLogger("midibot.panel")
HTML = Path(__file__).with_name("panel.html")


async def start_panel(bot, engine):
    routes = web.RouteTableDef()

    @routes.get("/")
    async def index(_):
        return web.FileResponse(HTML)

    @routes.get("/api/voices")
    async def voice_list(_):
        return web.json_response([voices.public(v) for v in voices.VOICES])

    @routes.get("/api/state")
    async def state(_):
        vc = bot.vc
        channels = [
            {"id": str(c.id), "name": c.name, "guild": g.name, "members": len(c.members)}
            for g in bot.guilds
            for c in g.voice_channels
            if c.permissions_for(g.me).connect
        ]
        return web.json_response({
            "online": bot.is_ready(),
            "user": str(bot.user) if bot.user else None,
            "keyboard": bot.midi.port.name.split(":")[0] if bot.midi.port else None,
            "notes": bot.midi.notes,
            "channel": {"id": str(vc.channel.id), "name": vc.channel.name, "guild": vc.guild.name} if vc else None,
            "encrypted": bot.dave_ready(),
            "privacy_code": vc.voice_privacy_code if vc else None,
            "channels": channels,
            "voice": voices.public(engine.voice),
            "dual_voice": voices.public(engine.dual_voice),
            "sound": engine.sound_name(engine.voice),
            "approximate": voices.sound_for(engine.voice)[2],
            "follow_keyboard": engine.follow_keyboard,
            "keyboard_out": bot.midi.out is not None,
            "volume": engine.volume,
            "reverb": engine.reverb,
            "level": round(engine.level, 3),
        })

    @routes.post("/api/join")
    async def join(req):
        data = await req.json()
        channel = bot.get_channel(int(data["channel_id"]))
        if not isinstance(channel, discord.VoiceChannel):
            return web.json_response({"error": "canal de voz não encontrado"}, status=404)
        await bot.join(channel)
        return web.json_response({"ok": True})

    @routes.post("/api/leave")
    async def leave(_):
        await bot.leave()
        return web.json_response({"ok": True})

    @routes.post("/api/sound")
    async def sound(req):
        data = await req.json()
        if "follow_keyboard" in data:
            engine.follow_keyboard = bool(data["follow_keyboard"])
        if "voice" in data:
            voice = voices.BY_NO[int(data["voice"])]
            engine.set_voice(voice)
            if engine.follow_keyboard:
                bot.midi.send_voice(voice)
        if "volume" in data:
            bot.set_volume(float(data["volume"]))
        if "reverb" in data:
            engine.set_reverb(float(data["reverb"]))
        return web.json_response({"ok": True})

    @routes.post("/api/demo")
    async def demo(_):
        bot.loop.create_task(engine.demo())
        return web.json_response({"ok": True})

    @routes.post("/api/panic")
    async def panic(_):
        engine.panic()
        return web.json_response({"ok": True})

    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    port = int(os.environ.get("PANEL_PORT", "8765"))
    await web.TCPSite(runner, "127.0.0.1", port).start()
    log.info("Painel em http://localhost:%d", port)
