# ICM42688 虚拟上位机

## 页面入口

启动 FastAPI 服务后打开：

```text
http://127.0.0.1:8081/imu
```

如果当前没有完整 Python/FastAPI 环境，也可以直接双击打开：

```text
templates/imu.html
```

直接打开时页面会自动进入“模拟模式”，可以先查看 3D 姿态物体、曲线、数值面板和 CSV 导出效果。

页面功能：

- 3D 姿态物体：显示 roll、pitch、yaw。
- 实时数值：显示加速度、角速度、模长、采样间隔、估计帧率。
- 状态判断：still、moving、tilted、rotating、impact。
- 历史曲线：姿态角曲线、加速度/角速度模长曲线。
- 调试控制：模拟模式、校准零点、暂停、清空曲线、导出 CSV。
- 原始 JSON：显示最近一帧数据，便于检查 ESP32 发送格式。

## UDP 数据格式

ESP32 或模拟器向服务器 `UDP 12345` 发送 UTF-8 JSON：

```json
{
  "ts": 1710000000000,
  "accel": {"x": 0.0, "y": 9.8, "z": 0.0},
  "gyro": {"x": 0.0, "y": 0.0, "z": 0.0}
}
```

兼容字段：

- `timestamp_ms` 会被服务端映射为 `ts`。
- `ts` 推荐使用毫秒时间戳。
- `accel` 单位建议为 `m/s^2`。
- `gyro` 单位建议为 `deg/s`。

服务端会通过 `/ws` 转发增强后的 JSON，额外包含：

- `angles`: roll、pitch、yaw。
- `metrics`: accel_norm、gyro_norm、still、near_flat。
- `state`: motion、still、near_flat。

## 无硬件测试

当前没有完整视觉/语音依赖时，优先启动零依赖 IMU 专用服务：

```powershell
python tools/imu_simple_server.py --host 127.0.0.1 --port 8081 --udp-port 12345
```

然后打开：

```text
http://127.0.0.1:8081/imu
```

如果完整项目依赖已经安装，也可以启动完整服务：

```powershell
python app_main.py
```

发送模拟 UDP：

```powershell
python tools/simulate_imu_udp.py --host 127.0.0.1 --port 12345 --hz 50 --seconds 60
```

打开 `/imu`，确认：

- `WS connected`。
- `live data`。
- 3D 物体持续转动。
- 曲线持续刷新。
- 导出 CSV 能生成历史数据。

也可以直接点页面里的“模拟模式”，此时不需要 UDP 输入。
