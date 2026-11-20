# 系统架构与接口

```text
ESP32 + OV3660 / 本地视频模拟器
  └─ JPEG → /ws/camera → FastAPI ┬─ /ws/viewer → /status 原始流栏
                                ├─ TrafficMonitor → /ws/traffic_viewer → /status 识别流栏
                                └─ 导航状态机 / 物品查找 → 叠加画面与语音提示
ESP32 麦克风 → /ws_audio → DashScope ASR → 指令解析 / Qwen-Omni → /ws_ui
本地提示音 / AI 语音 → WAV 下行 /stream.wav → ESP32 扬声器
ICM42688 → ESP32 → UDP 12345 → 姿态估计 → /ws → /imu
```

图中「原始流栏」指相对于交通识别流的常规视频订阅；导航或找物模式也可能在常规流上绘制标注。

## 模块入口

| 模块 | 路径 | 职责 |
| --- | --- | --- |
| 服务与设备通信 | [app_main.py](../app_main.py)、[bridge_io.py](../bridge_io.py) | 路由、最近帧、WebSocket 广播、设备状态、模式与线程协调 |
| 状态页 | [status.html](../templates/status.html)、[status.js](../static/status.js)、[status.css](../static/status.css) | JPEG 画布、浏览器 FPS 和帧龄、链路轮询、ASR 文本流 |
| 状态页交通识别 | [traffic_monitor.py](../traffic_monitor.py)、[yoloe_backend.py](../yoloe_backend.py) | 独立工作线程、YOLOE 类别提示词、ByteTrack 跟踪、框和计数 |
| 导航与找物 | [navigation_master.py](../navigation_master.py)、[workflow_blindpath.py](../workflow_blindpath.py)、[workflow_crossstreet.py](../workflow_crossstreet.py)、[trafficlight_detection.py](../trafficlight_detection.py)、[yolomedia.py](../yolomedia.py) | 导航状态机、分割和光流、红绿灯检测、开放词汇找物与手部检测 |
| 音频与大模型 | [asr_core.py](../asr_core.py)、[omni_client.py](../omni_client.py)、[audio_player.py](../audio_player.py)、[audio_stream.py](../audio_stream.py) | 实时识别事件处理、图文问答、提示音与语音回传 |
| 固件 | [PlatformIO 相机测试](../firmware_camera_status/README.md)、[完整固件](../compile/compile.ino) | 单独验收 JPEG 推流；完整版本再接音频和 IMU |

## 通信契约

| 接口 | 方向与数据 |
| --- | --- |
| `GET /`、`GET /status`、`GET /imu` | 主界面、硬件状态台、姿态界面 |
| `GET /api/health`、`GET /api/status` | 前者纯文本 `OK`；后者 JSON，包括相机/音频连接、最后帧龄、IMU 包龄、订阅数、交通识别状态 |
| `WS /ws/camera` | 设备或模拟器 → 服务；每条二进制消息是一张 JPEG |
| `WS /ws/viewer`、`WS /ws/traffic_viewer` | 服务 → 浏览器；常规与交通标注 JPEG 流 |
| `POST /api/traffic-monitor/start`、`POST /api/traffic-monitor/stop` | 状态页启动/停止服务端交通识别，影响所有订阅者 |
| `WS /ws_audio`、`GET /stream.wav` | 设备上传 PCM16 / 16 kHz 或控制消息；设备拉取语音 WAV 流 |
| `WS /ws_ui` | 服务 → 浏览器，`INIT:`、`PARTIAL:`、`FINAL:` 文本 |
| `UDP 12345`、`WS /ws` | 设备上报加速度/角速度 JSON；服务广播 `angles`、`accel`、`gyro`、`state` 等字段 |

## 关键行为与边界

- **实时性**：交通识别先加载模型，再从容量为 1 的队列取最新 JPEG。推理跟不上时覆盖旧帧，降低等待延迟；浏览器 FPS、服务器推理 FPS 与摄像头 FPS 不是同一个指标。
- **识别范围**：状态页跟踪行人、自行车、汽车、摩托车、公交车、卡车。红绿灯和斑马线走独立模块；不从单帧估算可靠车速、距离或通行安全性。
- **端边云分工**：ESP32 采集与传输；电脑做视觉模型推理、姿态估计和分发；仅启用语音/问答功能时调用云端。主服务在 `app_main.py` 使用 DashScope 实时 Paraformer；`tools/test_asr.py` 的本地 FunASR 是独立冒烟测试。
- **部署**：摄像头连接、订阅者和模型状态保存在当前进程，按单 worker 启动。浏览器重连只代表订阅恢复，摄像头是否正在发送要看最后帧龄。服务用于可信局域网，不具备公网访问所需的鉴权。
