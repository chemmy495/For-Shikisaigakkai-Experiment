/*
 * shikisai_led.ino
 * WS2812B LED色識別実験 - Arduino UNO 用スケッチ
 *
 * 必要ライブラリ: FastLED (Arduino IDEのライブラリマネージャからインストール)
 * 接続: WS2812B データ線 → Arduinoピン 6
 *
 * シリアルコマンド (9600 baud):
 *   SHOW R G B  → 全LEDを指定色で点灯 (R/G/B: 0-255)
 *   OFF         → 全LED消灯
 * 応答:
 *   READY       → 起動完了
 *   OK          → コマンド実行完了
 */

#include <FastLED.h>

#define LED_PIN     6
#define NUM_LEDS    8
#define LED_TYPE    WS2812B
#define COLOR_ORDER GRB
#define BRIGHTNESS  80   // 0-255 (実験環境に応じて調整)

CRGB leds[NUM_LEDS];

void setup() {
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);

  // 起動時に全消灯
  fill_solid(leds, NUM_LEDS, CRGB::Black);
  FastLED.show();

  Serial.begin(9600);
  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "OFF") {
      fill_solid(leds, NUM_LEDS, CRGB::Black);
      FastLED.show();
      Serial.println("OK");

    } else if (command.startsWith("SHOW ")) {
      int r = 0, g = 0, b = 0;
      // フォーマット: "SHOW R G B"
      sscanf(command.c_str(), "SHOW %d %d %d", &r, &g, &b);
      r = constrain(r, 0, 255);
      g = constrain(g, 0, 255);
      b = constrain(b, 0, 255);
      fill_solid(leds, NUM_LEDS, CRGB(r, g, b));
      FastLED.show();
      Serial.println("OK");
    }
  }
}
