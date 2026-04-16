# opp-server

Screen text reader + local AI assistant using macOS Accessibility API, Apple Vision OCR, and Ollama.
Reads visible text from any app **without interacting with it**, then feeds it to a local LLM.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

## Permissions (one-time)

| Permission | Where |
|---|---|
| **Accessibility** | System Settings → Privacy & Security → Accessibility → ✅ Terminal |
| **Screen Recording** | System Settings → Privacy & Security → Screen Recording → ✅ Terminal |

## Ollama setup (local AI)

```bash
# Install Ollama
brew install ollama

# Start the server
ollama serve

# Pull a model (in another tab)
ollama pull llama3.2
```

## Run: screen watcher only

```bash
# Plain text output
python -m opp_server.watcher --browser "Google Chrome" --interval 2

# JSON output
python -m opp_server.watcher --browser "Google Chrome" --interval 2 --json

# Full snapshot on every change
python -m opp_server.watcher --browser "Google Chrome" --interval 1 --full
```

## Run: screen watcher + AI assistant

```bash
# Auto mode — AI comments every time screen changes
python -m opp_server.pipeline --browser "Google Chrome" --model llama3.2

# Ask a specific question on each change
python -m opp_server.pipeline --browser "Google Chrome" \
  --question "What task or question is shown on screen?"

# Interactive mode — you type questions, AI answers based on current screen
python -m opp_server.pipeline --browser "Google Chrome" --interactive

# List available local models
python -m opp_server.pipeline --list-models
```

## Change AI model

```bash
# Use any model you have pulled
OLLAMA_MODEL=mistral python -m opp_server.pipeline --browser "Google Chrome"

# Or pass via flag
python -m opp_server.pipeline --model mistral --browser "Google Chrome"
```

## Supported apps

Any macOS app: Chrome, Safari, Firefox, Arc, Terminal, Electron apps, etc.

## External output: phone / ESP32 / wearable

### TCP (телефон по WiFi)

```bash
# Запустить с TCP каналом
python -m opp_server.pipeline \
  --browser "Google Chrome" \
  --model "qwen2.5-coder:7b" \
  --tcp 9999

# Подключиться с телефона (та же WiFi сеть)
nc <mac-ip> 9999
```

iOS: приложение **TCP Socket** или **Terminus**  
Android: **Serial Bluetooth Terminal** → TCP mode

---

### Bluetooth Serial (ESP32 / HC-05 / HC-06)

**Шаг 1** — Запаровать устройство в System Settings → Bluetooth

**Шаг 2** — Найти порт:
```bash
ls /dev/tty.* | grep -v Bluetooth
# Например: /dev/tty.HC-05
```

**Шаг 3** — Запустить pipeline с BT:
```bash
python -m opp_server.pipeline \
  --browser "Google Chrome" \
  --model "qwen2.5-coder:7b" \
  --bt "HC-05" \
  --baud 9600
```

**ESP32 Arduino код** для приёма:
```cpp
#include <BluetoothSerial.h>
BluetoothSerial SerialBT;

void setup() {
  Serial.begin(115200);
  SerialBT.begin("ESP32-AI");  // имя устройства
}

void loop() {
  if (SerialBT.available()) {
    String msg = SerialBT.readStringUntil('\n');
    Serial.println(msg);    // или вывести на дисплей / TTS
  }
}
```

**Тест канала без pipeline:**
```bash
# TCP тест
python -m opp_server.output_stream --tcp 9999

# BT тест  
python -m opp_server.output_stream --bt "HC-05"
```

### Одновременно TCP + BT + overlay:
```bash
python -m opp_server.pipeline \
  --browser "Google Chrome" \
  --model "qwen2.5-coder:7b" \
  --tcp 9999 \
  --bt "HC-05"
```

## Tests

```bash
python -m unittest discover -s tests -v
```

