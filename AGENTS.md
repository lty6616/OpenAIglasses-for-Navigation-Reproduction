# AI 接手指南

这是一个 FastAPI + ESP32 的交通场景识别演示原型。默认目标是在 Windows 上用仓库内的视频跑通 `/status`，不接硬件、不调用云端 API。项目不能作为真实导盲或通行判断依据。

## 先确认环境

1. 在含 `app_main.py` 和 `requirements.txt` 的仓库根目录执行命令。先看 `git status --short`；保留用户已有修改，不顺手重构。
2. 优先复用 Python 3.11 的 Conda 环境 `aiglass`。用 `python --version` 和 `python -m pip check` 确认解释器与依赖。缺环境时按[队友上手手册](docs/REPRODUCTION_GUIDE.md)安装，不要直接改动系统 Python。
3. 权重、`mobileclip_blt.ts` 和样例视频用 Git LFS 管理。用 `git lfs ls-files` 看文件是否已实装（`-` 表示指针，`*` 表示实际文件）；必要时运行 `git lfs pull`。用 `python tools/check_models.py` 检查模型路径。
4. 如需本地配置，仅在不存在 `.env` 时从 `.env.example` 复制。不读出或记录密钥，不覆盖既有配置。只排查页面且暂时没装好 Python 环境时，可按[状态页说明](docs/STATUS_MONITOR.md)运行 Node 模拟服务；它不执行真实识别。

## 最短验证路径

**终端 1：启动后端。** 先访问 `http://127.0.0.1:8081/api/health`。如果已有服务，确认是本项目且没有其他人正在联调，再复用。不要杀未知进程，不要同时启动争抢 TCP 8081 或 UDP 12345 的第二个服务。

```powershell
conda activate aiglass
$env:DASHSCOPE_API_KEY = "your_api_key_here"
python app_main.py
```

占位密钥只影响当前终端及其子进程。等待模型预热，确保 `/api/health` 返回纯文本 `OK`，并打开 `http://127.0.0.1:8081/status`。如显存不足或 CUDA 不可用，可在启动前设置 `$env:AIGLASS_DEVICE = "cpu"`。

**终端 2：推流。** 服务器只接受一个相机输入；有 ESP32 正在推流时，不要启动模拟器抢连接。

```powershell
conda activate aiglass
python tools/simulate_camera_client.py --video "samples/13239132-hd_1920_1080_50fps.mp4" --fps 5 --seconds 120 --loop
```

若视频或 LFS 暂不可用，去掉 `--video` 和 `--loop` 测试合成帧。合成帧只验证传输，不用于验证检测准确性。

**终端 3：在推流期间验证。**

```powershell
conda activate aiglass
python tools/verify_status_page.py
python tools/verify_traffic_monitor.py --timeout 45
```

- 原始视频：`verify_status_page.py` 必须实际收到 `/ws/viewer` 的 JPEG。若输出「跳过 viewer 测试」，即使末尾是 PASS，也不能算视频通过。
- 交通识别：`verify_traffic_monitor.py` 会启动全局交通识别并接收 `/ws/traffic_viewer` 的 JPEG；确认 `state=running`、`frames > 0`。也可在页面点击「启动交通识别」，切到「交通 AI」查看框和计数。没跑模型时，明确写「未验证识别」。
- 收尾：只退出自己启动的模拟器和服务；复用经同意的服务时，只撤销本次改变的识别状态。不要删除 `recordings/` 中的本地录制。

## 按问题读代码

| 问题 | 入口 |
| --- | --- |
| 服务、相机接入与广播 | `app_main.py`、`bridge_io.py` |
| 状态页或画面异常 | `templates/status.html`、`static/status.js`、`static/status.css` |
| YOLOE 和 ByteTrack | `traffic_monitor.py`、`yoloe_backend.py` |
| ESP32、UDP IMU 或云端语音 | [系统架构与协议](docs/ARCHITECTURE.md)、[队友上手手册](docs/REPRODUCTION_GUIDE.md)、[API 单项测试](docs/API_SMOKE_TESTS.md) |

排障顺序：健康接口 → 原始 JPEG → 交通标注 → 实物/云端。只有用户明确要求时才烧录固件、修改网络/防火墙、调用计费 API 或推送改动。不公开服务，不提交 `.env`、固件本地配置、日志或录音录像。

交接时报告：用的 Python 与设备、启动命令、哪一步实际通过、哪些步骤未测，以及失败时最先出现的错误。
