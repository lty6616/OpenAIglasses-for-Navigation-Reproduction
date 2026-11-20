# 队友上手手册

推荐顺序：**本地视频 → 模型识别 → ESP32 相机 → IMU / 语音**。仓库不包含测试视频、YOLO 权重或个人配置。它是学习和受控演示原型，不用于真实独立导盲或判断能否过马路。

## 1. Windows / VS Code 环境

接受 GitHub 仓库邀请后，在 PowerShell 执行：

```powershell
git clone https://github.com/lty6616/OpenAIglasses-for-Navigation-Reproduction.git
cd OpenAIglasses-for-Navigation-Reproduction
conda create -n aiglass python=3.11 -y
conda activate aiglass
python -m pip install -r requirements.txt
python -m pip check
Copy-Item .env.example .env
python tools/check_env.py
```

已有 `aiglass` 环境只需激活，不必重建；已有 `.env` 不要覆盖。在 VS Code 打开仓库根目录，通过 `Python: Select Interpreter` 选 `aiglass`。若当前终端找不到 `conda`，先用 Anaconda Prompt；没有 Conda 时也可用 Python 3.11 建 `venv`。`check_env.py` 会检查完整系统的模型；仅验证相机传输时，缺权重提示不代表服务不能启动。

只测试画面时，`DASHSCOPE_API_KEY` 保持占位即可。没有 NVIDIA GPU 时，在 `.env` 设 `AIGLASS_DEVICE=cpu`。有 NVIDIA GPU 时用 `nvidia-smi` 查看驱动，并通过以下命令确认**当前 Python 环境**的 PyTorch 可见 GPU：

```powershell
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

若已装 CPU 版且驱动支持 CUDA 11.8，可在该环境重装匹配的三件套，然后重跑检查：

```powershell
python -m pip install --upgrade "torch==2.0.1+cu118" "torchvision==0.15.2+cu118" "torchaudio==2.0.2+cu118" --index-url https://download.pytorch.org/whl/cu118
```

## 2. 不接 ESP32：跑本地视频

终端一（在仓库根目录，已激活环境）：

```powershell
python app_main.py
```

打开 [状态页](http://127.0.0.1:8081/status)；[健康检查](http://127.0.0.1:8081/api/health) 应返回纯文本 `OK`。终端二也激活 `aiglass`，先测试 30 秒合成帧：

```powershell
python tools/simulate_camera_client.py --fps 5 --seconds 30
```

有画面且 FPS 接近 5 后，将有权使用的测试视频放在 `samples/traffic.mp4`，或者把参数换成手头文件的路径：

```powershell
python tools/simulate_camera_client.py --video "samples/traffic.mp4" --fps 5 --seconds 120 --loop
```

此命令沿用 ESP32 的 WebSocket JPEG 协议，不需要挂接硬件，也不会把视频上传到云端。联调时仅运行一个输入源（ESP32 或模拟器）。服务会在本地 `recordings/` 写入录制数据。

只看界面布局、还没装好 Python 依赖时，可运行 `node tools/status_demo_server.js --host 127.0.0.1 --port 8081 --fps 5`。这是模拟页面服务，不会运行交通模型；不要与 FastAPI 同占 8081。

## 3. 模型文件

从[原项目 ModelScope 模型页](https://www.modelscope.cn/models/archifancy/AIGlasses_for_navigation)获取所需权重，放入仓库根目录的 `model/`，或用 `.env` 指定路径。找不到权重时先向队友确认版本，不要用同名的无关模型替代。

| 文件 | 配置项 | 用途 |
| --- | --- | --- |
| `yoloe-11l-seg.pt` | `YOLOE_MODEL_PATH`、`OBSTACLE_MODEL` | 状态页交通目标、开放词汇物品检测、障碍物 |
| `yolo-seg.pt` | `BLIND_PATH_MODEL` | 盲道与斑马线分割 |
| `trafficlight.pt` | `TRAFFIC_LIGHT_MODEL` | 专用红绿灯检测链路，不是状态页 YOLOE 标注 |
| `shoppingbest5.pt` | `SHOPPING_MODEL` | 物品查找后备模型 |
| `hand_landmarker.task` | `HAND_TASK_PATH` | 手部关键点，仓库已附 |

YOLOE 还使用 `mobileclip_blt.ts` 编码类别提示词。Ultralytics 通常会在首次使用时下载；若下载受网络限制，从 [Ultralytics 官方资产发布页](https://github.com/ultralytics/assets/releases/tag/v8.3.0)下载该文件，放到**仓库根目录**（与 `app_main.py` 同级），再从根目录启动服务。

本地权重放好后，运行 `python tools/check_models.py --load` 检查上表文件；只装了部分权重时，其余项会报告缺失。重启服务，在 `/status` 点击「启动交通识别」。有输入时应看到行人、车辆、自行车等类别的框和计数；是否检出取决于视频内容。可切回原始视频，对比帧率与识别结果。

## 4. 接入 XIAO ESP32S3 Sense + OV3660

1. 电脑与 ESP32 接入同一可信局域网。校园网若有网页认证或设备隔离，改用电脑或手机的 2.4 GHz 热点。
2. 先用 [PlatformIO 相机测试固件](../firmware_camera_status/README.md)。复制 `firmware_camera_status/include/aiglass_local_config.example.h` 为同目录的 `aiglass_local_config.h`，填写热点名、密码，以及 `ipconfig` 中同网段的**电脑 IPv4**，不能填 `127.0.0.1`。
3. 在 VS Code 单独打开 `firmware_camera_status/`，用 USB-C 数据线连接开发板，PlatformIO 执行 Upload，再打开 115200 波特率的 Serial Monitor。启动 FastAPI，确认串口有相机初始化、Wi-Fi 已连和 `[WS-CAM] open`；状态页帧数应持续增加。
4. 音频和 IMU 需要完整固件。将 `compile/config.example.h` 复制为 `compile/config.h`，填写本地参数，再按[接线清单](WIRING_CHECKLIST.md)和[IMU 手册](ICM42688_UPPER_COMPUTER.md)核对模块与引脚。这两套固件读取不同的配置文件。

若串口连上 Wi-Fi 但 WebSocket 未打开，优先排查 IPv4、TCP 8081、防火墙和热点隔离；IMU 另需 UDP 12345。仅对实验用可信网络放行，不将服务暴露到公网。

## 5. 给队友使用后端

`http://127.0.0.1:8081/status` **只在运行后端的那台电脑上有效**。GitHub 仓库提供源码和文档，不会替团队运行这个 FastAPI 服务。点击仓库里的本机地址时，浏览器访问的是读者自己的电脑。

| 情况 | FastAPI 跑在哪里 | 队友浏览器地址 | ESP32 的 `AIGLASS_SERVER_HOST` |
| --- | --- | --- | --- |
| 不同地点，各有硬件（推荐） | 每人自己的电脑，执行 `python app_main.py` | 各自打开 `http://127.0.0.1:8081/status` | 各自电脑与板子所在网络的 IPv4 |
| 同一实验室或同一热点，共用一台服务器 | 一台电脑持续运行 `python app_main.py` | `http://<服务器IPv4>:8081/status` | 同一个服务器 IPv4，不加 `http://` 或端口 |

**各自运行**：每位队友接受私有仓库邀请、克隆代码并按本手册建环境。把电脑和自己的 ESP32 接入同一个可互访的网络，在电脑运行 `ipconfig` 找对应网卡的 IPv4，写入本地固件配置并重新烧录。只看画面不必准备 API Key；要跑交通识别则每台电脑都需模型文件，语音/问答再各自配置密钥。

**同一局域网共用**：

1. 服务器电脑运行 `python app_main.py`，确认同机打开 `http://127.0.0.1:8081/api/health` 得到 `OK`。此命令监听 `0.0.0.0:8081`，其他设备访问时必须使用服务器的实际局域网地址。
2. 服务器、队友电脑和 ESP32 接同一个可信网络。用 `ipconfig` 找服务器在该网络的 IPv4。假如地址是 `192.168.137.1`，队友浏览器打开 `http://192.168.137.1:8081/status`，板子的 `AIGLASS_SERVER_HOST` 填 `"192.168.137.1"`，`AIGLASS_SERVER_PORT` 保持 `8081`。完整固件的 `AIGLASS_UDP_HOST` 指向同一服务器，端口 `12345`。
3. 在服务器 Windows 防火墙仅对可信网络或本地子网放行入站 TCP 8081；测试 IMU 时再放行 UDP 12345。在队友电脑先用浏览器访问 `http://<服务器IPv4>:8081/api/health`，或运行 `Test-NetConnection <服务器IPv4> -Port 8081`。若本机能打开而队友不能，先查是否入错网络、用错网卡 IP、被防火墙或校园网设备隔离拦住。
4. 队友能访问健康接口后，再烧录并检查串口的 Wi-Fi / WebSocket 日志。健康检查成功但状态页没画面时，看最后帧龄，确认模拟器已停止且 ESP32 仍在推送 JPEG。热点或网段变化后重新核对 IP，需要时重烧。

**共用限制**：现有后端是单套设备会话和全局导航/交通状态。可以多人观看，但一次只接一套硬件或一个模拟输入；多副眼镜同时测试应各跑一套后端。关掉服务器终端或让电脑休眠会断开连接。本服务没有登录鉴权，不要做公网端口映射；异地联调优先各自运行。

## 6. 分模块验证和协作

- **IMU**：访问 `/imu`，另一终端运行 `python tools/simulate_imu_udp.py --hz 50 --seconds 30`，观察姿态变化。
- **语音与问答**：先按 [API 单项测试](API_SMOKE_TESTS.md)验证 WAV 和单张图片。FunASR 的本地 Paraformer 测试与主服务的 DashScope 实时 ASR 不同，配置本地模型不会自动切换主服务。
- **排障顺序**：健康检查 → 原始画面 → 交通识别 → ESP32 链路。端口被占时先停掉自己启动的旧服务。视频连上但持续 0 FPS 时，检查输入进程、最后帧龄和串口日志。
- **团队协作**：从 `main` 创建功能分支，完成一条链路的验证后提 PR；记录输入、操作、预期和实际结果。不要提交 `.env`、两份本地固件配置、模型权重、录像或私人素材。
