/* 硬件状态监控台 —— 数据源协议（与服务器 app_main.py 现有端点一致，勿随意更改）：
   视频帧     ws(s)://host/ws/viewer    二进制消息 = JPEG 帧本体，无 JSON
   链路统计   http(s)://host/api/status JSON，3s 轮询
   服务器心跳 http(s)://host/api/health 纯文本 "OK"，不能按 JSON 解析
   语音文字流 ws(s)://host/ws_ui        文本前缀协议：INIT:<json> / PARTIAL:<text> / FINAL:<text>
*/
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';

  if (location.protocol === 'file:') {
    $('fileBanner').classList.remove('hidden');
  }

  function setBadge(el, cls, text) { el.className = `badge ${cls}`; el.textContent = text; }
  function setPill(el, cls, text) { el.className = `pill ${cls}`; el.textContent = text; }
  function nowHMS() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }); }

  /* ---------- 通用自动重连 WebSocket（指数退避 1/2/5/10s 封顶） ---------- */
  function liveWs(path, { onopen, onmessage, onclose } = {}) {
    let ws = null, attempt = 0, timer = null, closedByUs = false;
    const delays = [1000, 2000, 5000, 10000];

    function connect() {
      try {
        ws = new WebSocket(`${proto}://${location.host}${path}`);
      } catch (e) {
        schedule();
        return;
      }
      ws.binaryType = 'arraybuffer';
      ws.onopen = () => { attempt = 0; if (onopen) onopen(ws); };
      ws.onmessage = (ev) => { if (onmessage) onmessage(ev, ws); };
      ws.onerror = () => { try { ws.close(); } catch (e) { /* noop */ } };
      ws.onclose = () => { if (onclose) onclose(); if (!closedByUs) schedule(); };
    }
    function schedule() {
      const d = delays[Math.min(attempt, delays.length - 1)];
      attempt += 1;
      clearTimeout(timer);
      timer = setTimeout(connect, d);
    }
    connect();
    return {
      close() {
        closedByUs = true;
        clearTimeout(timer);
        try { if (ws) ws.close(); } catch (e) { /* noop */ }
      },
    };
  }

  /* ---------- 顶栏：时钟 + 服务器心跳 ---------- */
  const serverPill = $('serverPill');
  const uptimePill = $('uptimePill');
  const clockPill = $('clockPill');
  let serverUp = null;

  setInterval(() => { clockPill.textContent = nowHMS(); }, 1000);
  clockPill.textContent = nowHMS();

  function humanUptime(sec) {
    if (sec == null) return '运行 --';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    return h > 0 ? `运行 ${h}时${m}分` : m > 0 ? `运行 ${m}分${s}秒` : `运行 ${s}秒`;
  }

  async function pollHealth() {
    try {
      const r = await fetch('/api/health', { cache: 'no-store' });
      const ok = (await r.text()).trim() === 'OK';
      if (ok !== serverUp) {
        serverUp = ok;
        setPill(serverPill, ok ? '' : 'err', ok ? '服务器在线' : '服务器异常');
      }
    } catch (e) {
      if (serverUp !== false) {
        serverUp = false;
        setPill(serverPill, 'err', '服务器离线');
        setPill(uptimePill, 'muted', '运行 --');
      }
    }
  }
  pollHealth();
  setInterval(pollHealth, 3000);

  /* ---------- 实时视频：/ws/viewer 二进制 JPEG ---------- */
  const canvas = $('videoCanvas');
  const ctx = canvas.getContext('2d');
  const videoBadge = $('videoWsBadge');
  const placeholder = $('videoPlaceholder');
  const streamAlert = $('streamAlert');
  const btnRawStream = $('btnRawStream');
  const btnTrafficStream = $('btnTrafficStream');
  const videoEndpoint = $('videoEndpoint');
  let fpsFrames = 0;
  let fpsWindowStart = 0;
  let totalFrames = 0;
  let lastFramePerf = 0;
  let gotResolution = false;
  let decodeBusy = false;
  let pendingFrame = null;
  let videoSocket = null;
  let activeVideoPath = '/ws/viewer';

  function paintFrame(buf) {
    const blob = new Blob([buf], { type: 'image/jpeg' });
    const show = (bmp, w, h) => {
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      ctx.drawImage(bmp, 0, 0, w, h);
      if (!gotResolution) {
        $('statRes').textContent = `${w}×${h}`;
        gotResolution = true;
      }
    };
    const done = () => {
      decodeBusy = false;
      if (pendingFrame) {
        const next = pendingFrame;
        pendingFrame = null;
        queueDecode(next);
      }
    };
    if ('createImageBitmap' in window) {
      createImageBitmap(blob)
        .then((b) => { show(b, b.width, b.height); if (b.close) b.close(); })
        .catch(() => {})
        .finally(done);
    } else {
      const img = new Image();
      img.onload = () => {
        show(img, img.naturalWidth, img.naturalHeight);
        URL.revokeObjectURL(img.src);
        done();
      };
      img.onerror = () => { URL.revokeObjectURL(img.src); done(); };
      img.src = URL.createObjectURL(blob);
    }
  }

  // 解码落后时丢弃中间帧，只保留最新帧，防止队列和内存无限增长。
  function queueDecode(buf) {
    if (decodeBusy) {
      pendingFrame = buf;
      return;
    }
    decodeBusy = true;
    paintFrame(buf);
  }

  function receiveFrame(buf) {
    totalFrames += 1;
    fpsFrames += 1;
    lastFramePerf = performance.now();
    placeholder.classList.add('hidden');
    streamAlert.classList.add('hidden');
    $('statSize').textContent = `${(buf.byteLength / 1024).toFixed(1)} KB`;
    $('statTotal').textContent = String(totalFrames);
    queueDecode(buf);
  }

  setInterval(() => {
    const now = performance.now();
    if (fpsWindowStart) {
      const dt = (now - fpsWindowStart) / 1000;
      $('statFps').textContent = (fpsFrames / Math.max(dt, 0.001)).toFixed(1);
    }
    fpsFrames = 0;
    fpsWindowStart = now;
    if (lastFramePerf) {
      const age = (now - lastFramePerf) / 1000;
      const el = $('statAge');
      el.textContent = age < 60 ? `${age.toFixed(1)}s` : `${Math.floor(age / 60)}分+`;
      el.style.color = age > 3 ? 'var(--yellow)' : 'var(--green)';
      streamAlert.classList.toggle('hidden', age <= 3);
    }
  }, 1000);

  function connectVideo(path) {
    if (path === activeVideoPath && videoSocket) return;
    if (videoSocket) videoSocket.close();
    activeVideoPath = path;
    videoEndpoint.textContent = path;
    btnRawStream.classList.toggle('selected', path === '/ws/viewer');
    btnTrafficStream.classList.toggle('selected', path === '/ws/traffic_viewer');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    placeholder.classList.remove('hidden');
    placeholder.querySelector('p').textContent = path === '/ws/viewer' ? '等待原始视频流…' : '等待交通识别画面…';
    streamAlert.classList.add('hidden');
    lastFramePerf = 0;
    fpsFrames = 0;
    fpsWindowStart = performance.now();
    gotResolution = false;
    $('statFps').textContent = '--';
    $('statRes').textContent = '--';
    $('statSize').textContent = '--';
    $('statAge').textContent = '--';

    videoSocket = liveWs(path, {
      onopen: () => setBadge(videoBadge, 'ok', '已连接'),
      onmessage: (ev) => { if (ev.data instanceof ArrayBuffer) receiveFrame(ev.data); },
      onclose: () => setBadge(videoBadge, 'off', '重连中…'),
    });
  }

  btnRawStream.addEventListener('click', () => connectVideo('/ws/viewer'));
  btnTrafficStream.addEventListener('click', () => connectVideo('/ws/traffic_viewer'));
  activeVideoPath = '';
  connectVideo('/ws/viewer');

  /* ---------- 数据链路卡片：/api/status 3s 轮询 ---------- */
  const cards = {
    camera: {
      dot: $('dotCamera'), state: $('stateCamera'), esp: $('camEsp'), age: $('camAge'),
    },
    audio: {
      dot: $('dotAudio'), state: $('stateAudio'), esp: $('audEsp'),
    },
    imu: {
      dot: $('dotImu'), state: $('stateImu'), age: $('imuAge'), clients: $('imuClients'),
    },
  };

  const trafficUi = {
    badge: $('trafficBadge'),
    toggle: $('btnTrafficToggle'),
    model: $('trafficModelState'),
    latency: $('trafficLatency'),
    fps: $('trafficFps'),
    frames: $('trafficFrames'),
    counts: $('trafficCounts'),
    tracks: $('trafficTracks'),
    error: $('trafficError'),
  };
  const trafficLabels = {
    person: '行人', bicycle: '自行车', car: '汽车', motorcycle: '摩托车', bus: '公交车', truck: '卡车',
  };
  const trafficColors = {
    person: 'var(--green)', bicycle: 'var(--cyan)', car: 'var(--blue)',
    motorcycle: 'var(--yellow)', bus: '#ff8c5a', truck: 'var(--red)',
  };
  let trafficRunning = false;

  function renderTraffic(monitor = {}) {
    const state = monitor.state || 'idle';
    trafficRunning = state === 'running' || state === 'loading';
    const stateText = {
      idle: '未启动', loading: '加载中…', running: '运行中', stopping: '停止中…', error: '启动失败',
    }[state] || state;
    const badgeClass = state === 'running' ? 'ok' : (state === 'error' ? 'err' : (state === 'loading' || state === 'stopping' ? 'warn' : 'off'));
    setBadge(trafficUi.badge, badgeClass, stateText);
    trafficUi.model.textContent = monitor.model_loaded ? 'YOLOE + ByteTrack' : stateText;
    trafficUi.latency.textContent = monitor.inference_ms == null ? '--' : `${monitor.inference_ms} ms`;
    trafficUi.fps.textContent = monitor.processing_fps ? `${monitor.processing_fps} FPS` : '--';
    trafficUi.frames.textContent = String(monitor.processed_frames || 0);
    trafficUi.toggle.disabled = state === 'loading' || state === 'stopping';
    trafficUi.toggle.classList.toggle('running', state === 'running');
    trafficUi.toggle.textContent = state === 'running' ? '停止交通识别' : (state === 'loading' ? '正在加载模型' : '启动交通识别');

    trafficUi.counts.innerHTML = '';
    const counts = monitor.counts || {};
    Object.keys(trafficLabels).filter((name) => counts[name]).forEach((name) => {
      const chip = document.createElement('span');
      chip.className = 'count-chip';
      chip.style.borderLeftColor = trafficColors[name];
      const label = document.createElement('span');
      label.textContent = trafficLabels[name];
      const count = document.createElement('b');
      count.textContent = String(counts[name]);
      chip.append(label, count);
      trafficUi.counts.appendChild(chip);
    });
    if (!trafficUi.counts.children.length) {
      trafficUi.counts.innerHTML = '<span class="empty-text">暂无目标</span>';
    }

    trafficUi.tracks.innerHTML = '';
    (monitor.detections || []).slice(0, 14).forEach((item) => {
      const el = document.createElement('span');
      el.className = 'track-item';
      const id = item.track_id == null ? '--' : `#${item.track_id}`;
      el.textContent = `${trafficLabels[item.name] || item.name} ${id}`;
      const confidence = document.createElement('small');
      confidence.textContent = `${Math.round((item.confidence || 0) * 100)}%`;
      el.appendChild(confidence);
      trafficUi.tracks.appendChild(el);
    });
    if (!trafficUi.tracks.children.length) {
      trafficUi.tracks.innerHTML = '<span class="empty-text">暂无追踪结果</span>';
    }

    trafficUi.error.textContent = monitor.error || '';
    trafficUi.error.classList.toggle('hidden', !monitor.error);
  }

  async function setTrafficMonitorEnabled(enabled) {
    trafficUi.toggle.disabled = true;
    connectVideo(enabled ? '/ws/traffic_viewer' : '/ws/viewer');
    try {
      const path = enabled ? '/api/traffic-monitor/start' : '/api/traffic-monitor/stop';
      const r = await fetch(path, { method: 'POST' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      renderTraffic(await r.json());
    } catch (e) {
      if (enabled) connectVideo('/ws/viewer');
      renderTraffic({ state: 'error', error: `控制请求失败：${e.message}` });
    }
  }

  trafficUi.toggle.addEventListener('click', () => setTrafficMonitorEnabled(!trafficRunning));

  function setCard(card, level, stateText) {
    card.dot.className = `dot ${level}`;
    card.state.className = `state ${level}`;
    card.state.textContent = stateText;
  }

  function fmtAge(ms) {
    if (ms == null) return '--';
    if (ms < 1000) return `${ms} ms 前`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)} s 前`;
    return `${Math.floor(ms / 60000)}分${Math.floor((ms % 60000) / 1000)}秒前`;
  }

  async function pollStatus() {
    let d;
    try {
      const r = await fetch('/api/status', { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      d = await r.json();
    } catch (e) {
      setCard(cards.camera, 'off', '服务器不可达');
      setCard(cards.audio, 'off', '服务器不可达');
      setCard(cards.imu, 'off', '服务器不可达');
      return;
    }

    // 摄像头链路：ESP32 WebSocket 握手 + 最后帧龄双重判断
    const camAge = d.last_frame_age_ms;
    if (d.camera_esp32_connected) {
      if (camAge != null && camAge > 5000) setCard(cards.camera, 'warn', '已连接但帧流超时');
      else setCard(cards.camera, 'ok', '在线');
    } else if (d.demo_stream_active) {
      setCard(cards.camera, 'warn', '模拟画面');
    } else if (camAge != null && camAge < 3000) {
      setCard(cards.camera, 'warn', '有帧流但未握手');
    } else {
      setCard(cards.camera, 'off', '未连接');
    }
    cards.camera.esp.textContent = d.camera_esp32_connected ? '已连接' : '未连接';
    cards.camera.age.textContent = fmtAge(camAge);

    // 音频链路：/ws_audio 上行通道
    setCard(cards.audio, d.audio_esp32_connected ? 'ok' : 'off',
      d.audio_esp32_connected ? '在线' : '未连接');
    cards.audio.esp.textContent = d.audio_esp32_connected ? '已连接' : '未连接';

    // IMU 链路：UDP 12345 收包新鲜度
    const imuAge = d.last_imu_age_ms;
    if (imuAge == null) setCard(cards.imu, 'off', '无 UDP 数据');
    else if (imuAge < 2000) setCard(cards.imu, 'ok', '数据流正常');
    else if (imuAge < 10000) setCard(cards.imu, 'warn', '数据超时');
    else setCard(cards.imu, 'off', '数据中断');
    cards.imu.age.textContent = fmtAge(imuAge);
    cards.imu.clients.textContent = `${d.imu_client_count} 个浏览器`;

    $('subCounts').textContent =
      `订阅：视频 ${d.viewer_count} · 文字流 ${d.ui_client_count} · IMU ${d.imu_client_count}`;
    $('navState').textContent =
      `导航：${d.navigation_active ? '进行中' : '空闲'} · 物品查找：${d.yolomedia_running ? '运行' : '停止'}`;
    setPill(uptimePill, '', humanUptime(d.uptime_sec));
    renderTraffic(d.traffic_monitor);
  }
  pollStatus();
  setInterval(pollStatus, 3000);

  /* ---------- 语音识别文字流：/ws_ui 前缀协议 ---------- */
  const asrList = $('asrList');
  const asrPartial = $('asrPartial');
  const asrBadge = $('asrBadge');

  function classify(text) {
    if (text.startsWith('[AI]')) return { tag: 'AI', cls: 'ai', body: text.slice(4).trim() };
    if (text.startsWith('[导航]')) return { tag: '导航', cls: 'nav', body: text.slice(4).trim() };
    if (text.startsWith('[系统]')) return { tag: '系统', cls: 'sys', body: text.slice(4).trim() };
    return { tag: '用户', cls: 'user', body: text };
  }

  function addLog(text) {
    if (!text) return;
    const c = classify(text);
    const div = document.createElement('div');
    div.className = 'log-entry';
    const t = document.createElement('span');
    t.className = 't';
    t.textContent = nowHMS();
    const tag = document.createElement('span');
    tag.className = `tag ${c.cls}`;
    tag.textContent = c.tag;
    const txt = document.createElement('span');
    txt.className = 'txt';
    txt.textContent = c.body;
    div.appendChild(t);
    div.appendChild(tag);
    div.appendChild(txt);
    asrList.appendChild(div);
    while (asrList.children.length > 100) asrList.removeChild(asrList.firstChild);
    asrList.scrollTop = asrList.scrollHeight;
  }

  liveWs('/ws_ui', {
    onopen: () => setBadge(asrBadge, 'ok', '已连接'),
    onmessage: (ev) => {
      const s = ev.data || '';
      if (s.startsWith('INIT:')) {
        try {
          const data = JSON.parse(s.slice(5));
          asrPartial.textContent = data.partial || '（等待音频…）';
          // 仅在空列表时回放历史，避免重连后重复
          if (asrList.children.length === 0) {
            (data.finals || []).slice(-20).forEach(addLog);
          }
        } catch (e) { /* 忽略坏帧 */ }
      } else if (s.startsWith('PARTIAL:')) {
        asrPartial.textContent = s.slice(8) || '（等待音频…）';
      } else if (s.startsWith('FINAL:')) {
        addLog(s.slice(6));
        asrPartial.textContent = '（等待音频…）';
      }
    },
    onclose: () => setBadge(asrBadge, 'off', '重连中…'),
  });

  $('btnClearAsr').addEventListener('click', () => { asrList.innerHTML = ''; });
})();
