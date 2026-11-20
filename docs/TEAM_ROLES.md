# 团队分工与阶段执行计划

> 本文档基于三人分工方案（A 算法与模型 / B 后端服务与硬件通信 / C 前端与全栈集成）制定，
> 与 `REPRODUCTION_PLAN.md`（旧版 A=嵌入式/B=算法/C=音视频）的代号不同，映射关系见文末。
> 各阶段时间节点对齐大创考核：中期检查约 2027 年 3-4 月，结题约 2028 年 3 月。

---

## 一、分工总览与代码对应

### 🅰️ 成员 A — 算法与模型（代码量最大，约 7800 行）

| 模块 | 文件 | 行数 |
| --- | --- | --- |
| 盲道导航 | `workflow_blindpath.py` | 3261 |
| 过马路辅助 | `workflow_crossstreet.py` | 1817 |
| 物品查找 | `yolomedia.py` | 1571 |
| 红绿灯检测 | `trafficlight_detection.py` | 622 |
| 斑马线感知 | `crosswalk_awareness.py` | 342 |
| YOLO-E 后端 | `yoloe_backend.py` | 83 |
| 意图解析 | `qwen_extractor.py` | 63 |
| 模型文件 | `model/`（4 个 .pt 待下载） | — |
| 冒烟测试 | `tools/offline_vision_smoke.py` | — |

### 🅱️ 成员 B — 后端服务与硬件通信（负载第二，且卡在最早的关键路径上）

| 模块 | 文件 | 行数 |
| --- | --- | --- |
| 主服务 | `app_main.py` | 1369 |
| 导航状态机 | `navigation_master.py` | 700 |
| 录制 | `sync_recorder.py` | 322 |
| 语音播放 | `audio_player.py` | 393 |
| ASR | `asr_core.py` | 204 |
| 音频流 | `audio_stream.py` | 151 |
| 帧分发 | `bridge_io.py` | 92 |
| Omni 客户端 | `omni_client.py` | 73 |
| 固件 | `compile/compile.ino` + `config.example.h` | — |
| 环境配置 | `config.py`、`requirements.txt`、`.env` | — |

### 🅲 成员 C — 前端与全栈集成（前端已基本写好，定位是验收 + 增强 + 集成 + 文档）

| 模块 | 文件 | 状态 |
| --- | --- | --- |
| 主监控页 | `templates/index.html` + `static/main.js`（845 行） | 已有，需验收适配 |
| 视频渲染 | `static/vision.js`、`vision_renderer.js` | 已有 |
| IMU 可视化 | `templates/imu.html` + `static/imu_dashboard.js` | 已有（6 月新增） |
| 状态可视化 | `static/visualizer.js` | 已有 |
| 检查工具 | `tools/check_env.py`、`check_models.py`、`check_audio_assets.py` | 已有 |
| 模拟器 | `tools/simulate_camera_client.py`、`simulate_imu_udp.py` | 已有 |
| 协作文档 | `docs/`、`README`、演示视频、答辩 PPT | 待建 |

---

## 二、分工风险评估与两条修正

1. **B 是阶段 1 的瓶颈**：固件 + 服务 + 音频 + 稳定性全压在 B 身上。
   缓解：固件已经写好（`compile.ino` v2.4 已参数化），B 的任务是烧录调参而非从零开发；
   「DashScope 云端 API 可用性验证」（`tools/test_asr.py`、`tools/test_omni.py`）拆给 C 先行验证，
   B 只负责把验证通过的 API 接进服务管线；ESP32 摄像头参数（分辨率/JPEG 质量）由 A 配合调优。

2. **C 早期容易空转、A 早期任务偏轻**：
   C 在阶段 0 承担版本管理（当前没有有效的 Git 仓库，`F:\竞赛\大创\.git` 是坏的）、
   云服务验证、部署文档；A 在阶段 0-1 提前通读三大工作流源码并画流程图、搭单元测试骨架，
   为阶段 2 的攻坚做准备。

3. **单点风险**：每个模块指定一名「第二读者」（A↔B 互读对方核心文件，C 通读全部接口），
   每周日在 `docs/TEAM_TRACKER.md` 记录周会，避免再次出现 7 月那种全员停滞。

---

## 三、阶段 × 成员任务矩阵

### Phase 0：解除阻塞（2026-09 上旬，1-2 周）

| 成员 | 任务 | 个人里程碑 |
| --- | --- | --- |
| A | ① Python 3.11 venv + `requirements.txt` + CUDA 版 torch；② 下载 4 个模型到 `model/`；③ `tools/offline_vision_smoke.py` 跑通 blindpath / shopping / traffic 三种模式；④ 开始通读 `workflow_blindpath.py` 画流程图 | 四个模型全部加载成功，一张盲道图片离线推理出分割结果 |
| B | ① 同上环境；② `python app_main.py` 服务器空转无报错，`/api/health` 返回 OK；③ `simulate_camera_client.py` + `simulate_imu_udp.py` 验证；④ Arduino IDE + ESP32 板包 + `ArduinoWebsockets`/`ESP_I2S` 库，XIAO 点灯 | 服务器空转 + 浏览器看到模拟摄像头画面（不需要任何硬件） |
| C | ① 在本代码目录 `git init`（根目录 `F:\竞赛\大创\.git` 是坏的，不要在那里 init），确认 `.gitignore` 已排除 `.env`/`config.h`/`model/*.pt`；② 建 main/dev 分支并推远端私有仓库；③ 申请 DashScope Key 填入 `.env`，跑通 `tools/test_asr.py` 和 `tools/test_omni.py`；④ 浏览器 bring-up 前端页面 | Git 仓库就绪 + DashScope 两个测试脚本跑通 + 前端页面正常打开 |

**阶段总里程碑：软件链路全部就绪，只等硬件到货。**

### Phase 1：最小可运行系统 MVP（2026-09 中 - 10 中）

| 成员 | 任务 | 个人里程碑 |
| --- | --- | --- |
| A | ① 配合 B 调 ESP32 摄像头参数（`framesize`、JPEG 质量、抽帧），在画质与带宽间取舍；② 用真实拍摄素材测分割模型鲁棒性（不同光照/磨损盲道）；③ 搭好 pytest 单元测试骨架 | 实时视频流下分割推理 < 100ms/帧（RTX 4060） |
| B | ① 烧录 `compile.ino`（复制 `config.example.h` → `config.h`，填 WiFi/服务器 IP）；② ESP32 视频上浏览器；③ MAX98357 + 喇叭接线，`/stream.wav` 推流到喇叭出声；④ 麦克风 PCM16 上行到服务器 | 🏁 眼镜画面上浏览器 + 服务器语音从喇叭播出 |
| C | ① 验收前端：状态栏、FPS 显示、多客户端观看；② 记录第一段演示素材；③ 写「环境搭建指南」入 docs/；④ 周报机制运转 | 前端在真实视频流下稳定显示，第一支演示视频片段产出 |

**阶段总里程碑：MVP 双向闭环（图传上去、语音下来）。**

### Phase 2：三大功能逐一点亮（2026-10 中 - 12 月，A 主攻）

| 成员 | 任务 | 个人里程碑 |
| --- | --- | --- |
| A | 按「盲道 → 过马路 → 物品查找」顺序，**离线视频先行**跑通三大工作流：每条链路先用手机实拍视频离线调试，再接实时流；建立参数调整记录表（置信度阈值、光流参数、播报间隔） | 三大功能离线视频全部跑通，参数记录表成形 |
| B | ① 语音指令全链路（`start_ai_with_text_custom`）：逐条验证「开始导航/开始过马路/帮我找一下X/检测红绿灯/停止导航/帮我看看」；② 状态机切换联调；③ 音频优先级队列（导航播报打断 AI 对话） | 语音指令 → 状态切换 → 语音反馈全链路跑通 |
| C | ① 状态面板增强：展示当前导航状态、检测结果、置信度；② 联调测试表（`docs/TEST_MATRIX.md`）逐项验收；③ 每个功能录制验收视频 | 三大功能的实时链路验收单全部打勾 |

**阶段总里程碑：三大功能在真实硬件 + 实时链路上各跑通一次。**

### Phase 3：整机联调 + 场地测试 + 中期检查（2027-01 - 03）

| 成员 | 任务 | 个人里程碑 |
| --- | --- | --- |
| A | ① 真实盲道场地测试，调置信度阈值与播报间隔；② 极端光照鲁棒性测试与对策；③ 中期材料技术章节 | 场地测试数据 + 参数记录表定稿 |
| B | ① 断线重连（WiFi 断/服务器重启后 ESP32 自动恢复）；② 1 小时连续压测；③ 多客户端并发；④ 移动供电方案（充电宝带笔记本+眼镜） | 连续 1 小时不崩溃，断网自恢复 |
| C | ① 主导完整链路联调：盲道 → 发现斑马线 → 等绿灯 → 过马路 → 找对面盲道；② 完整演示视频 + 剪辑；③ 中期检查 PPT + 对着 `立项答辩/问题.docx` 逐条准备答辩口径 | 中期检查材料包提交 |

**阶段总里程碑：🏁 中期检查通过。**

### Phase 4：二次开发创新点（2027-04 起，决定结题质量）

| 成员 | 创新任务 |
| --- | --- |
| A | ① 自采盲道/斑马线数据集微调 YOLO（解决不同城市盲道泛化，可出软著/论文）；② 断网保底算法：轻量障碍检测/光流改进在边侧离线运行 |
| B | ① ESP32-S3 端侧轻量推理（断网应急避障）；② 自制集成 PCB：XIAO + ICM42688 + MAX98357 打样（`xiao esp32/` 已备好 KiCad 封装库，申报书承诺项） |
| C | ① 导盲杖原型（ToF + 超声波 + 振动反馈）的界面与系统集成；② 组织模拟视障用户测试，收集反馈迭代；③ 结题材料 |

---

## 四、各成员两周学习清单（对齐新分工）

### 🅰️ A（约 2-3 周）
- [ ] PyTorch GPU 推理基础：张量、device、half 精度
- [ ] OpenCV：掩码操作、形态学、骨架化、`cv2.calcOpticalFlowPyrLK` 光流
- [ ] Ultralytics：分割/检测任务、置信度与 IoU、ByteTrack 追踪（docs.ultralytics.com）
- [ ] MediaPipe Tasks 手部关键点（21 点）
- [ ] 推理调优手段：`imgsz`、抽帧、显存管理

### 🅱️ B（约 2-3 周）
- [ ] FastAPI + WebSocket：异步路由、后台任务、连接管理
- [ ] Python 线程安全：`queue.Queue`、锁、生产者-消费者（读 `bridge_io.py`）
- [ ] 音频基础：PCM16 / 16000Hz / 单声道 / 分块 / WAV 头结构（读 `audio_stream.py`）
- [ ] ESP32 烧录全流程：Arduino IDE 2.x、ESP32 板包 URL、串口调试
- [ ] 逐个读懂 `/ws/camera`、`/ws/viewer`、`/ws_audio`、`/stream.wav` 的报文格式

### 🅲 C（约 2 周）
- [ ] 前端 WebSocket 客户端 + Canvas 帧渲染（读 `static/main.js`）
- [ ] Three.js 场景基础（以 `static/imu_dashboard.js` 为练习对象）
- [ ] Git 团队工作流：main/dev 分支、commit 规范、PR 自查
- [ ] DashScope 控制台：开通、配额、计费监控、Key 轮换
- [ ] 演示录制工具链：OBS 录屏 + 剪辑

---

## 五、协作规则

1. **周会**：每周日晚 30 分钟，每人 3 件事（本周完成/下周计划/卡点），记入 `TEAM_TRACKER.md`。
2. **第二读者制**：`workflow_*.py` 第二读者 B，`app_main.py` 第二读者 A，全部接口文档第二读者 C。
3. **参数记录表**：所有调过的阈值/参数必须记录（文件名 + 参数名 + 旧值 → 新值 + 原因 + 效果），这是中期和结题的证明材料。
4. **Git 规范**：dev 开发、main 稳定；`.env`、`config.h`、`model/*.pt` 永不入库；每周日 main 打 tag。
5. **安全声明**：本项目为学习/原型用途，任何场地测试不得让视障人士在无陪护情况下实际使用。

---

## 六、新旧计划代号映射（避免与旧版 REPRODUCTION_PLAN.md 混淆）

| 旧计划代号 | 内容 | 新分工归属 |
| --- | --- | --- |
| 旧 A（嵌入式） | ESP32 接线、烧录、WiFi | **新 B**（A 配合调参） |
| 旧 B（AI 后端） | YOLO 推理、三大工作流 | **新 A** |
| 旧 C（音视频+集成） | DashScope、音频、前端 | ASR/Omni 云端验证 → **新 C**；音频管线与服务 → **新 B**；前端 → **新 C** |
