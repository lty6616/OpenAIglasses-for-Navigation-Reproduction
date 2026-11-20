# Team Tracker

> 分工定义见 `docs/TEAM_ROLES.md`：A 算法与模型 / B 后端服务与硬件 / C 前端与集成。
> 每周日例会记录：本周完成 / 下周计划 / 卡点。

## Weekly Meeting

| Week | Date | A 算法与模型 | B 服务与硬件 | C 前端与集成 | Decisions |
|---|---|---|---|---|---|
| 1 |  |  |  |  |  |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |
| 4 |  |  |  |  |  |
| 5 |  |  |  |  |  |
| 6 |  |  |  |  |  |
| 7 |  |  |  |  |  |
| 8 |  |  |  |  |  |
| 9 |  |  |  |  |  |
| 10 |  |  |  |  |  |
| 11 |  |  |  |  |  |
| 12 |  |  |  |  |  |

## Issue Template

```text
Issue ID:
Date:
Owner:
Module:
Reproduction steps:
Expected:
Actual:
Logs:
Attempted fixes:
Final resolution:
Remaining risk:
```

## Role Checklist

## Current Sprint: Hardware Status Monitor

- [x] `/status` Chinese dashboard and responsive single-page layout implemented.
- [x] `/ws/viewer` JPEG canvas, FPS, resolution, frame size, total frames, and frame age implemented.
- [x] `/api/status` camera/audio/IMU link cards implemented without changing transport protocols.
- [x] `/ws_ui` INIT/PARTIAL/FINAL text stream and automatic WebSocket reconnect implemented.
- [x] 5 FPS mock stream verified at 5.0-5.1 FPS; two browser tabs verified concurrently.
- [x] Server stop/start recovery verified without manually refreshing the page.
- [ ] Real ESP32 camera stream verified by member B on the same LAN.
- [ ] Real PCM16 audio and ICM42688 UDP activity verified with hardware.

### A: 算法与模型

- [ ] Python 3.11 venv + CUDA PyTorch verified (`torch.cuda.is_available()` is True).
- [ ] Four model files downloaded into `model/` and loaded (`tools/check_models.py --load`).
- [ ] Offline vision smoke tests run (blindpath / shopping / traffic).
- [ ] Blindpath workflow verified on offline video with correct guidance text.
- [ ] Crossstreet workflow verified on offline video (crosswalk + traffic light states).
- [ ] Item search workflow verified on offline video (YOLO-E + hand guidance).
- [ ] Parameter tuning log started (thresholds, intervals).
- [ ] Realtime inference < 100 ms/frame on RTX 4060.

### B: 后端服务与硬件通信

- [ ] Server boots with no ESP32; `/api/health` returns OK.
- [ ] Simulated camera client and IMU UDP simulator verified.
- [ ] Firmware flashed with `config.h`; camera stream connects to `/ws/camera`.
- [ ] ESP32 video visible in browser viewer.
- [ ] MAX98357 speaker wiring verified; `/stream.wav` playback on ESP32 speaker.
- [ ] Mic PCM16 upload reaches server; ASR text visible.
- [ ] All voice commands trigger correct state transitions.
- [ ] Reconnect after WiFi/server restart; 1-hour soak test passed.

### C: 前端与全栈集成

- [ ] Git repo initialized (inside code folder), main/dev branches, remote private repo pushed.
- [ ] `.env` / `config.h` / `model/*.pt` confirmed excluded from version control.
- [ ] DashScope key configured; `tools/test_asr.py` and `tools/test_omni.py` pass.
- [ ] Web frontend verified on real video stream (status bar, FPS, multi-client).
- [ ] `docs/TEST_MATRIX.md` acceptance items checked for each feature.
- [ ] Environment setup guide written into `docs/`.
- [ ] Demo video clips captured per milestone.
- [ ] Demo script and safety statement drafted.
