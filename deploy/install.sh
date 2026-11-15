#!/usr/bin/env bash
# Instala o TecladoLindinhoBOT como serviço systemd num servidor Linux com o teclado plugado na USB.
# Uso (dentro da pasta do projeto, como o usuário que vai rodar o bot):  ./deploy/install.sh
set -euo pipefail

cd "$(dirname "$0")/.."
DIR="$(pwd)"
USER_NAME="$(id -un)"
SERVICE=teclado-bot

echo "==> Dependências do sistema (FluidSynth + soundfont)"
if command -v pacman >/dev/null; then
    sudo pacman -S --needed --noconfirm fluidsynth soundfont-fluid alsa-utils
elif command -v apt-get >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y fluidsynth fluid-soundfont-gm alsa-utils curl
else
    echo "Gerenciador de pacotes não reconhecido: instale fluidsynth e um soundfont GM na mão."
fi

if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
    echo "==> Instalando uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"

echo "==> Dependências Python (o uv baixa o Python 3.14 se precisar)"
"$UV" sync

if [ ! -f .env ]; then
    cp .env.example .env
    echo "==> Criei o .env. Coloque o DISCORD_TOKEN nele antes de iniciar o bot."
fi

# Acesso ao sequenciador MIDI do ALSA (/dev/snd/seq) sem sessão gráfica
if getent group audio >/dev/null && ! id -nG "$USER_NAME" | grep -qw audio; then
    echo "==> Adicionando $USER_NAME ao grupo audio"
    sudo usermod -aG audio "$USER_NAME"
fi

echo "==> Criando o serviço /etc/systemd/system/$SERVICE.service"
sudo tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<EOF
[Unit]
Description=TecladoLindinhoBOT (teclado MIDI ao vivo no Discord)
Wants=network-online.target
After=network-online.target sound.target

[Service]
User=$USER_NAME
SupplementaryGroups=audio
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python bot.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"

cat <<EOF

Pronto. Próximos passos:
  1. Edite $DIR/.env e coloque o DISCORD_TOKEN (e LOCAL_MONITOR vazio).
  2. Plugue o teclado e confira se ele aparece:  aconnect -i
  3. Inicie:      sudo systemctl start $SERVICE
     Logs:        journalctl -u $SERVICE -f
  4. Painel, a partir do seu PC:  ssh -L 8765:localhost:8765 $USER_NAME@<ip-do-servidor>
     e abra http://localhost:8765
EOF
