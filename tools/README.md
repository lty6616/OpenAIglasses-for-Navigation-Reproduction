# Reproduction Helper Tools

Run these commands from the project directory:

```powershell
python tools/check_env.py
python tools/check_models.py
python tools/check_models.py --load
python tools/check_audio_assets.py
python tools/test_asr.py path\to\recording.wav
python tools/test_asr.py path\to\recording.wav --mode server --server-url http://127.0.0.1:8000/v1/audio/transcriptions
python tools/test_omni.py path\to\image.jpg --prompt "请描述图片里的障碍物"
python tools/simulate_imu_udp.py --host 127.0.0.1 --port 12345 --hz 50 --seconds 30
python tools/simulate_camera_client.py --host 127.0.0.1 --port 8081 --fps 5 --seconds 30
python tools/simulate_camera_client.py --video samples\13239132-hd_1920_1080_50fps.mp4 --fps 10 --seconds 60 --loop --width 960 --height 540
python tools/verify_traffic_monitor.py --host 127.0.0.1 --port 8081
python tools/offline_vision_smoke.py path\to\image.jpg --mode blindpath --output blindpath_smoke.jpg
node tools/status_demo_server.js --host 127.0.0.1 --port 8081 --fps 5
```

Expected workflow:

1. `check_env.py`: verify Python packages, CUDA visibility, DashScope configuration, and model file presence.
2. `check_models.py`: confirm files exist; use `--load` only after dependencies and GPU are ready.
3. `simulate_camera_client.py`: test `/ws/camera` and browser `/ws/viewer` before touching ESP32.
   Use `--video` to replay a traffic video through exactly the same camera protocol.
4. `offline_vision_smoke.py`: test one still image with blindpath, shopping, traffic, or hand mode.
5. `check_audio_assets.py`: verify local prerecorded voice mappings before audio integration.
6. `test_asr.py`: recognize one WAV file with local FunASR/Paraformer by default, or a local FunASR server with `--mode server`.
7. `test_omni.py`: send one image plus text to Qwen-Omni through DashScope/OpenAI compatibility mode. It needs `DASHSCOPE_API_KEY` in `.env`.
8. `simulate_imu_udp.py`: send synthetic ICM42688-like UDP packets to test `/imu` and `/ws` without hardware.
9. `status_demo_server.js`: preview and test `/status` with a 5 FPS local JPEG stream before FastAPI, models, or ESP32 are ready.
10. `verify_traffic_monitor.py`: with ESP32 or the video simulator active, start the YOLOE + ByteTrack monitor and verify `/ws/traffic_viewer` plus live statistics.

Live traffic recognition:

```powershell
python app_main.py
python tools/simulate_camera_client.py --video samples\13239132-hd_1920_1080_50fps.mp4 --fps 10 --seconds 60 --loop --width 960 --height 540
```

Open `http://127.0.0.1:8081/status`, click **启动交通识别**, and keep **交通 AI** selected. The first start loads a second YOLOE instance and can take several seconds. The page then shows class counts, ByteTrack IDs, inference latency, and the annotated stream.

Status monitor preview (no Python packages or models required):

```powershell
node tools/status_demo_server.js --host 127.0.0.1 --port 8081 --fps 5
```

Then open `http://127.0.0.1:8081/status`. Use `--host 0.0.0.0 --fps 0` when receiving a real ESP32 `/ws/camera` stream through this lightweight integration server.

IMU virtual upper-computer:

```powershell
python app_main.py
python tools/simulate_imu_udp.py --host 127.0.0.1 --port 12345 --hz 50 --seconds 60
```

Then open `http://127.0.0.1:8081/imu`. The page also has a built-in mock mode, so it can be used before the backend receives UDP packets.
