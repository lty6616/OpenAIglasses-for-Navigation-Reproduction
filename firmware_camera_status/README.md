# XIAO ESP32S3 Camera Status Smoke Test

This PlatformIO project isolates the camera-to-browser link from audio, IMU, ASR, and AI dependencies.

## Network

Campus Wi-Fi may use web/enterprise authentication or client isolation. For the first test, connect both the computer and XIAO ESP32S3 to the same phone hotspot or Windows mobile hotspot.

Copy `include/aiglass_local_config.example.h` to `include/aiglass_local_config.h`. Fill in the hotspot SSID and password and set `AIGLASS_SERVER_HOST` to the computer's IPv4 address on that network (check with `ipconfig`). This firmware does not read `../compile/config.h`.

## VS Code / PlatformIO

1. Open the `firmware_camera_status` folder in VS Code.
2. Let PlatformIO install the Espressif 32 platform and `ArduinoWebsockets` library.
3. Connect the XIAO ESP32S3 through USB-C.
4. Click PlatformIO `Upload`.
5. Click PlatformIO `Serial Monitor`; it uses 115200 baud.

Expected serial output:

```text
[BOOT] PSRAM=yes
[CAM] sensor PID=0x3660
[WiFi] ... OK
[WS-CAM] open
[CAM] fps=...
```

The status page camera card changes from yellow `模拟画面` to green `在线` when the real WebSocket connects.
