#include <Arduino.h>
#include <ArduinoWebsockets.h>
#include <WiFi.h>
#include <esp_camera.h>

#include "aiglass_local_config.h"

using namespace websockets;

namespace {
constexpr int kPwdn = -1;
constexpr int kReset = -1;
constexpr int kXclk = 10;
constexpr int kSiod = 40;
constexpr int kSioc = 39;
constexpr int kY9 = 48;
constexpr int kY8 = 11;
constexpr int kY7 = 12;
constexpr int kY6 = 14;
constexpr int kY5 = 16;
constexpr int kY4 = 18;
constexpr int kY3 = 17;
constexpr int kY2 = 15;
constexpr int kVsync = 38;
constexpr int kHref = 47;
constexpr int kPclk = 13;
constexpr uint32_t kFrameIntervalMs = 100;  // 10 FPS target.

WebsocketsClient camera_ws;
bool websocket_ready = false;
uint32_t last_connect_attempt_ms = 0;
uint32_t last_frame_ms = 0;
uint32_t stats_started_ms = 0;
uint32_t sent_frames = 0;
uint32_t failed_frames = 0;
uint8_t consecutive_send_failures = 0;

bool init_camera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = kY2;
  config.pin_d1 = kY3;
  config.pin_d2 = kY4;
  config.pin_d3 = kY5;
  config.pin_d4 = kY6;
  config.pin_d5 = kY7;
  config.pin_d6 = kY8;
  config.pin_d7 = kY9;
  config.pin_xclk = kXclk;
  config.pin_pclk = kPclk;
  config.pin_vsync = kVsync;
  config.pin_href = kHref;
  config.pin_sccb_sda = kSiod;
  config.pin_sccb_scl = kSioc;
  config.pin_pwdn = kPwdn;
  config.pin_reset = kReset;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = psramFound() ? FRAMESIZE_VGA : FRAMESIZE_QVGA;
  config.jpeg_quality = 15;
  config.fb_count = psramFound() ? 2 : 1;
  config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.grab_mode = psramFound() ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;

  const esp_err_t error = esp_camera_init(&config);
  if (error != ESP_OK) {
    Serial.printf("[CAM] init failed: 0x%x\n", error);
    return false;
  }

  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor) {
    Serial.printf("[CAM] sensor PID=0x%04x\n", sensor->id.PID);
    sensor->set_hmirror(sensor, 1);
  }
  Serial.printf("[CAM] ready, PSRAM=%s\n", psramFound() ? "yes" : "no");
  return true;
}

void connect_wifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(AIGLASS_WIFI_SSID, AIGLASS_WIFI_PASS);
  Serial.printf("[WiFi] connecting to %s", AIGLASS_WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');
  }
  Serial.printf(" OK, IP=%s\n", WiFi.localIP().toString().c_str());
}

void configure_websocket() {
  camera_ws.onEvent([](WebsocketsEvent event, String) {
    if (event == WebsocketsEvent::ConnectionOpened) {
      websocket_ready = true;
      consecutive_send_failures = 0;
      Serial.println("[WS-CAM] open");
    } else if (event == WebsocketsEvent::ConnectionClosed) {
      websocket_ready = false;
      Serial.println("[WS-CAM] closed");
    }
  });
}

void connect_websocket_if_needed() {
  if (camera_ws.available()) return;
  websocket_ready = false;
  const uint32_t now = millis();
  if (now - last_connect_attempt_ms < 1000) return;
  last_connect_attempt_ms = now;

  // ArduinoWebsockets may retain an invalid ESP32 socket after the server
  // disappears. A fresh client keeps reconnects from getting stuck on EBADF.
  camera_ws.close();
  camera_ws = WebsocketsClient();
  configure_websocket();
  Serial.printf("[WS-CAM] connecting ws://%s:%u/ws/camera\n",
                AIGLASS_SERVER_HOST, AIGLASS_SERVER_PORT);
  if (camera_ws.connect(AIGLASS_SERVER_HOST, AIGLASS_SERVER_PORT, "/ws/camera")) {
    Serial.println("[WS-CAM] connected");
  } else {
    Serial.println("[WS-CAM] retry");
  }
}

void send_camera_frame() {
  const uint32_t now = millis();
  if (!websocket_ready || now - last_frame_ms < kFrameIntervalMs) return;
  last_frame_ms = now;

  camera_fb_t* frame = esp_camera_fb_get();
  if (!frame) {
    failed_frames += 1;
    return;
  }
  const bool sent = frame->format == PIXFORMAT_JPEG &&
                    camera_ws.sendBinary(reinterpret_cast<const char*>(frame->buf), frame->len);
  esp_camera_fb_return(frame);
  if (sent) {
    sent_frames += 1;
    consecutive_send_failures = 0;
  } else {
    failed_frames += 1;
    consecutive_send_failures += 1;
    if (consecutive_send_failures >= 3) {
      Serial.println("[WS-CAM] send timeout, reconnecting");
      websocket_ready = false;
      consecutive_send_failures = 0;
      camera_ws.close();
    }
  }

  if (now - stats_started_ms >= 2000) {
    const float fps = sent_frames * 1000.0f / static_cast<float>(now - stats_started_ms);
    Serial.printf("[CAM] fps=%.1f sent=%lu failed=%lu RSSI=%d\n",
                  fps, sent_frames, failed_frames, WiFi.RSSI());
    sent_frames = 0;
    failed_frames = 0;
    stats_started_ms = now;
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[XIAO] camera status smoke test");
  Serial.printf("[BOOT] PSRAM=%s, bytes=%u\n",
                psramFound() ? "yes" : "no", ESP.getPsramSize());
  if (!init_camera()) {
    Serial.println("[CAM] stop: check board, PSRAM, ribbon cable and camera driver");
    while (true) delay(1000);
  }
  connect_wifi();
  configure_websocket();
  stats_started_ms = millis();
}

void loop() {
  connect_websocket_if_needed();
  camera_ws.poll();
  send_camera_frame();
  delay(1);
}
