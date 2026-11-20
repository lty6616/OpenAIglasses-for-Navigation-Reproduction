# Hardware Status Monitor

The `/status` page is the browser-side acceptance tool for ESP32 camera, audio, IMU, and UI text links. It uses the production endpoint contracts and does not modify frame or audio transport behavior.

## Preview Before the Full Environment Is Ready

This path needs Node.js only. It serves the real status page and emits a local 5 FPS JPEG stream:

```powershell
node tools/status_demo_server.js --host 127.0.0.1 --port 8081 --fps 5
```

Open `http://127.0.0.1:8081/status`. Expected results:

- Server, camera, video viewer, and UI text stream show online.
- FPS stays between 4 and 6.
- Resolution shows `960x540` and total frames keep increasing.
- Opening a second tab changes video and UI subscriber counts to 2.

Press `Ctrl+C` to stop the demo server. The page should show offline/reconnecting within 3 seconds. Restart the same command; all links should recover without refreshing the page.

## Use the Production FastAPI Server

After the Python environment is complete:

```powershell
python app_main.py
python tools/simulate_camera_client.py --host 127.0.0.1 --port 8081 --fps 5 --seconds 60
```

Open `http://127.0.0.1:8081/status`. The simulator sends binary JPEG frames to `/ws/camera`; the server relays processed frames through `/ws/viewer`.

## Connect the Real ESP32

1. Put the ESP32 and computer on the same Wi-Fi network.
2. Run `ipconfig` and use the computer's LAN IPv4 address in `compile/config.h`.
3. Set the server port to `8081`, camera path to `/ws/camera`, and IMU UDP port to `12345`.
4. Allow inbound TCP 8081 and UDP 12345 in Windows Firewall.
5. Start the server on all interfaces:

```powershell
python app_main.py
```

6. Open `http://127.0.0.1:8081/status` on the computer, or `http://<computer-ip>:8081/status` from another device.
7. Power the ESP32 and check its 115200 baud serial log. The camera card should turn green and frame age should remain below 1 second.

## Endpoint Contract

| Source | Endpoint | Payload |
|---|---|---|
| ESP32 camera | `WS /ws/camera` | Binary JPEG frame |
| Browser viewer | `WS /ws/viewer` | Binary JPEG frame |
| ESP32 audio | `WS /ws_audio` | PCM16 16 kHz data or control text |
| UI text | `WS /ws_ui` | `INIT:`, `PARTIAL:`, `FINAL:` prefixed text |
| ESP32 IMU | `UDP 12345` | JSON accel/gyro/timestamp packet |
| Link statistics | `GET /api/status` | JSON status snapshot |
| Server heartbeat | `GET /api/health` | Plain text `OK` |

The demo server also accepts a real `/ws/camera` connection. Start it with `--host 0.0.0.0 --fps 0` when the full FastAPI service cannot yet boot; this isolates camera/WebSocket debugging from model dependencies.
