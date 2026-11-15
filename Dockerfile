# TecladoLindinhoBOT em container. O teclado MIDI chega via /dev/snd (veja compose.yaml).
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS build
# python-rtmidi não tem wheel para o Python 3.14: compila com os headers do ALSA
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config libasound2-dev \
    && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        libasound2 libfluidsynth3 fluid-soundfont-gm libopus0 alsa-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY *.py psr_e333_voices.json panel.html ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
CMD ["python", "bot.py"]
