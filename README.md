# 🎹 TecladoLindinhoBOT

Bot de Discord que toca um teclado MIDI **ao vivo** numa call de voz. Ele lê as notas do teclado pela USB,
sintetiza o som com o [FluidSynth](https://www.fluidsynth.org/) e manda o áudio para o canal de voz.

Foi feito para o **Yamaha PSR-E333**, com sincronização das 497 vozes do teclado, mas funciona com
qualquer teclado ou controlador MIDI USB.

## Recursos

- **Toca ao vivo na call:** o áudio é gerado no próprio processo, em blocos de 20 ms, sem roteamento de áudio do sistema.
- **Painel web local** (`http://localhost:8765`): entrar e sair da call, escolher o timbre, volume, reverb, medidor de saída e teste de som.
- **Sincroniza o timbre com o teclado:** trocar a voz no PSR-E333 troca o som do bot, e escolher no painel troca a voz do teclado. A voz dual (camada) também é suportada.
- **Comandos slash:** `/entrar`, `/sair`, `/instrumento <voz>` (com autocompletar pelo nome) e `/volume`.
- **Reconecta sozinho** se o teclado for desplugado e plugado de novo.
- **Monitor local opcional:** ouve no PC sem o atraso do Discord.

## Como funciona

```
Teclado ──MIDI──▶ mido / python-rtmidi ──▶ FluidSynth (soundfont GM, 48 kHz)
                                                   │ 20 ms de PCM por vez
                                     discord.py ◀──┘ ──Opus + E2EE (DAVE)──▶ call
```

## Requisitos

- Linux com ALSA/PipeWire (testado no Arch)
- Python ≥ 3.14 e [uv](https://docs.astral.sh/uv/)
- FluidSynth e um soundfont GM:
  ```sh
  sudo pacman -S fluidsynth soundfont-fluid   # Arch
  sudo apt install fluidsynth fluid-soundfont-gm   # Debian/Ubuntu
  ```

## Instalação

```sh
git clone https://github.com/danluan/TecladoLindinhoBOT.git
cd TecladoLindinhoBOT
uv sync
cp .env.example .env
```

### Criar o bot no Discord

1. Em <https://discord.com/developers/applications>, clique em **New Application**. Na aba **Bot**, use **Reset Token** e cole o token em `DISCORD_TOKEN` no `.env`.
2. Em **OAuth2 → URL Generator**, marque os scopes `bot` e `applications.commands` e as permissões **Connect**, **Speak** e **Use Voice Activity**. Abra a URL gerada para convidar o bot.
3. (Opcional) Coloque o ID do servidor em `GUILD_ID` para os comandos slash aparecerem na hora.

## Uso

```sh
uv run bot.py
```

Abra **http://localhost:8765**, escolha o canal de voz e clique em **Entrar**. Depois é só tocar.

### Configuração (`.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `DISCORD_TOKEN` | — | Token do bot (obrigatório) |
| `GUILD_ID` | — | Servidor onde os comandos slash são registrados na hora |
| `VOICE` | `1` | Voz inicial, pelo número do PSR-E333 (`88` = Ocarina) |
| `FOLLOW_KEYBOARD` | `1` | Sincroniza o timbre entre o teclado e o bot |
| `LOCAL_MONITOR` | vazio | `1` = também toca nos alto-falantes do PC |
| `MIDI_PORT` | `DigitalKBD` | Trecho do nome da porta MIDI do teclado |
| `SOUNDFONT` | FluidR3_GM | Caminho de um `.sf2`/`.sf3` |
| `PANEL_PORT` | `8765` | Porta do painel (só aceita conexões de `localhost`) |

## Sobre as vozes do PSR-E333

`psr_e333_voices.json` traz as 497 vozes do teclado (número no visor, banco MSB/LSB, programa e categoria),
extraídas da lista de vozes do [manual oficial](https://usa.yamaha.com/files/download/other_assets/1/322071/psre333_en_om_a0.pdf).
O som que vai para o Discord vem do soundfont GM, então as vozes exclusivas da Yamaha (variações XG, kits de efeitos)
tocam com o equivalente GM mais próximo. Nesses casos o painel mostra "(aproximado)".

## Observações

- **Latência:** espere de 150 a 300 ms até o som chegar à call. É o atraso normal da voz do Discord.
- **Criptografia de voz (DAVE):** o Discord exige E2EE nas calls. O `davey` está fixado em `<0.2`, porque a versão 0.2.0 mudou a API e quebra o discord.py 2.7.1: o bot conecta, mas ninguém ouve o áudio.
- A pasta `pilots/` tem os testes isolados de cada etapa: leitura MIDI, síntese local, renderização e voz no Discord.
