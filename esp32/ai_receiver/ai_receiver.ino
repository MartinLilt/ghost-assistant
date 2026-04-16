/*
  ai_receiver.ino — ESP32 Bluetooth Serial receiver for opp-server pipeline.

  Receives AI responses streamed from macOS via Classic Bluetooth (SPP/RFCOMM).
  Outputs to Serial Monitor. Ready to extend with OLED display or TTS.

  SETUP:
    1. Flash this sketch to ESP32
    2. On Mac: System Settings → Bluetooth → pair "ESP32-AI"
    3. Find port:  ls /dev/tty.* | grep ESP32
    4. Run pipeline:
         python -m opp_server.pipeline \
           --browser "Google Chrome" \
           --model "qwen2.5-coder:7b" \
           --bt "ESP32-AI" --baud 115200

  WIRING (optional OLED SSD1306 128x64, I2C):
    SDA → GPIO 21
    SCL → GPIO 22
    VCC → 3.3V
    GND → GND
*/

#include "BluetoothSerial.h"

// ── Config ──────────────────────────────────────────────────────────────────
#define DEVICE_NAME    "ESP32-AI"   // Bluetooth device name visible on Mac
#define BAUD_RATE      115200
#define MAX_LINE_LEN   512          // max chars per AI response line

// Optional: uncomment to enable SSD1306 OLED
// #define USE_OLED
#ifdef USE_OLED
  #include <Wire.h>
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>
  #define OLED_WIDTH 128
  #define OLED_HEIGHT 64
  Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
#endif

// ── Globals ─────────────────────────────────────────────────────────────────
BluetoothSerial SerialBT;
String lineBuffer = "";
bool   connected  = false;

// Built-in LED: ON when BT client connected
#define LED_PIN 2

// ── Setup ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  SerialBT.begin(DEVICE_NAME);
  Serial.println("[ESP32] Bluetooth started: " DEVICE_NAME);
  Serial.println("[ESP32] Waiting for connection from Mac...");

#ifdef USE_OLED
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[ESP32] OLED init failed");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(WHITE);
    display.setCursor(0, 0);
    display.println("AI Assistant");
    display.println("Waiting for BT...");
    display.display();
  }
#endif
}

// ── Helpers ──────────────────────────────────────────────────────────────────
void onConnect() {
  connected = true;
  digitalWrite(LED_PIN, HIGH);
  Serial.println("\n[BT] Mac connected!");
#ifdef USE_OLED
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Connected!");
  display.display();
#endif
}

void onDisconnect() {
  connected = false;
  digitalWrite(LED_PIN, LOW);
  Serial.println("\n[BT] Disconnected. Waiting...");
}

void handleLine(const String& line) {
  if (line.length() == 0) return;

  // Print to Serial Monitor
  Serial.println(line);

#ifdef USE_OLED
  // Scroll OLED: clear and show last few words
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  // Wrap at 21 chars per line (128px / 6px per char)
  int start = 0;
  int row = 0;
  while (start < (int)line.length() && row < 7) {
    String chunk = line.substring(start, start + 21);
    display.setCursor(0, row * 9);
    display.println(chunk);
    start += 21;
    row++;
  }
  display.display();
#endif
}

// ── Main loop ────────────────────────────────────────────────────────────────
void loop() {
  // Detect connect / disconnect via available()
  bool bt_available = SerialBT.hasClient();
  if (bt_available && !connected) onConnect();
  if (!bt_available && connected) onDisconnect();

  // Read incoming bytes
  while (SerialBT.available()) {
    char c = (char)SerialBT.read();

    if (c == '\n') {
      // Full line received — process it
      lineBuffer.trim();
      handleLine(lineBuffer);
      lineBuffer = "";
    } else if (c != '\r') {
      lineBuffer += c;
      // Safety: flush very long lines
      if (lineBuffer.length() >= MAX_LINE_LEN) {
        handleLine(lineBuffer);
        lineBuffer = "";
      }
    }
  }

  delay(10);
}

