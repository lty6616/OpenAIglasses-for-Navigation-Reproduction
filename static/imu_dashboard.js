(function () {
  const $ = (id) => document.getElementById(id);
  const state = {
    ws: null,
    mock: false,
    paused: false,
    lastPacketAt: 0,
    lastTs: 0,
    offsets: { roll: 0, pitch: 0, yaw: 0 },
    latest: null,
    history: [],
    maxHistory: 600,
    pollTimer: null,
  };

  const els = {
    wsState: $("wsState"),
    dataState: $("dataState"),
    bodyModel: $("bodyModel"),
    motionState: $("motionState"),
    rollValue: $("rollValue"),
    pitchValue: $("pitchValue"),
    yawValue: $("yawValue"),
    accelNorm: $("accelNorm"),
    gyroNorm: $("gyroNorm"),
    dtValue: $("dtValue"),
    rateValue: $("rateValue"),
    axValue: $("axValue"),
    ayValue: $("ayValue"),
    azValue: $("azValue"),
    gxValue: $("gxValue"),
    gyValue: $("gyValue"),
    gzValue: $("gzValue"),
    rawJson: $("rawJson"),
    lastTime: $("lastTime"),
    angleChart: $("angleChart"),
    motionChart: $("motionChart"),
    btnMock: $("btnMock"),
    btnZero: $("btnZero"),
    btnPause: $("btnPause"),
    btnClear: $("btnClear"),
    btnCsv: $("btnCsv"),
  };

  function setPill(el, text, kind) {
    el.textContent = text;
    el.className = "pill" + (kind ? " " + kind : "");
  }

  function num(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function vec(input) {
    const src = input || {};
    return {
      x: num(src.x),
      y: num(src.y),
      z: num(src.z),
    };
  }

  function wrap180(angle) {
    let out = angle % 360;
    if (out >= 180) out -= 360;
    if (out < -180) out += 360;
    return out;
  }

  function estimateAngles(accel, previousYaw) {
    const roll = Math.atan2(accel.z, accel.y) * 180 / Math.PI;
    const pitch = Math.atan2(-accel.x, Math.hypot(accel.y, accel.z)) * 180 / Math.PI;
    return { roll, pitch, yaw: previousYaw || 0 };
  }

  function normalizePacket(raw) {
    const accel = vec(raw.accel || { x: raw.ax, y: raw.ay, z: raw.az });
    const gyro = vec(raw.gyro || { x: raw.gx, y: raw.gy, z: raw.gz });
    const fallback = estimateAngles(accel, state.latest?.angles?.yaw || 0);
    const angles = {
      roll: num(raw.angles?.roll, fallback.roll),
      pitch: num(raw.angles?.pitch, fallback.pitch),
      yaw: num(raw.angles?.yaw, fallback.yaw),
    };
    const accelNorm = num(raw.metrics?.accel_norm, Math.hypot(accel.x, accel.y, accel.z));
    const gyroNorm = num(raw.metrics?.gyro_norm, Math.hypot(gyro.x, gyro.y, gyro.z));
    const still = Boolean(raw.state?.still ?? raw.metrics?.still ?? (Math.abs(accelNorm - 9.80665) < 0.8 && gyroNorm < 0.4));
    return {
      ts: num(raw.ts, Date.now()),
      server_time: num(raw.server_time, Date.now() / 1000),
      dt: num(raw.dt, 0),
      angles,
      accel,
      gyro,
      metrics: {
        accel_norm: accelNorm,
        gyro_norm: gyroNorm,
        still,
        near_flat: Boolean(raw.state?.near_flat ?? raw.metrics?.near_flat),
      },
      state: {
        motion: raw.state?.motion || (still ? "still" : "moving"),
      },
      raw,
    };
  }

  function applyOffsets(angles) {
    return {
      roll: wrap180(angles.roll - state.offsets.roll),
      pitch: wrap180(angles.pitch - state.offsets.pitch),
      yaw: wrap180(angles.yaw - state.offsets.yaw),
    };
  }

  function pushHistory(packet, displayAngles) {
    const now = performance.now();
    let dtMs = 0;
    if (state.lastPacketAt > 0) dtMs = now - state.lastPacketAt;
    state.lastPacketAt = now;
    state.lastTs = packet.ts;

    const sample = {
      time: now,
      roll: displayAngles.roll,
      pitch: displayAngles.pitch,
      yaw: displayAngles.yaw,
      accelNorm: packet.metrics.accel_norm,
      gyroNorm: packet.metrics.gyro_norm,
      dtMs: packet.dt ? packet.dt * 1000 : dtMs,
    };
    state.history.push(sample);
    if (state.history.length > state.maxHistory) {
      state.history.splice(0, state.history.length - state.maxHistory);
    }
    return sample;
  }

  function updateUi(packet) {
    const displayAngles = applyOffsets(packet.angles);
    const sample = pushHistory(packet, displayAngles);
    state.latest = packet;

    els.bodyModel.style.transform =
      `rotateZ(${displayAngles.yaw.toFixed(2)}deg) rotateX(${-displayAngles.pitch.toFixed(2)}deg) rotateY(${displayAngles.roll.toFixed(2)}deg)`;

    els.rollValue.textContent = `${displayAngles.roll.toFixed(1)}°`;
    els.pitchValue.textContent = `${displayAngles.pitch.toFixed(1)}°`;
    els.yawValue.textContent = `${displayAngles.yaw.toFixed(1)}°`;
    els.accelNorm.textContent = packet.metrics.accel_norm.toFixed(2);
    els.gyroNorm.textContent = packet.metrics.gyro_norm.toFixed(2);
    els.dtValue.textContent = Math.max(0, sample.dtMs).toFixed(0);
    els.rateValue.textContent = sample.dtMs > 0 ? (1000 / sample.dtMs).toFixed(1) : "0";
    els.axValue.textContent = packet.accel.x.toFixed(2);
    els.ayValue.textContent = packet.accel.y.toFixed(2);
    els.azValue.textContent = packet.accel.z.toFixed(2);
    els.gxValue.textContent = packet.gyro.x.toFixed(2);
    els.gyValue.textContent = packet.gyro.y.toFixed(2);
    els.gzValue.textContent = packet.gyro.z.toFixed(2);

    els.motionState.textContent = packet.state.motion;
    els.motionState.style.background = motionColor(packet.state.motion);
    els.lastTime.textContent = new Date().toLocaleTimeString();
    els.rawJson.textContent = JSON.stringify(packet.raw, null, 2);
    setPill(els.dataState, state.mock ? "mock data" : "live data", state.mock ? "warn" : "");
    drawCharts();
  }

  function motionColor(motion) {
    if (motion === "still") return "#5df2a5";
    if (motion === "impact") return "#ff6b6b";
    if (motion === "tilted") return "#ffd166";
    if (motion === "rotating") return "#6ea8fe";
    return "#5bd8ff";
  }

  function handlePacket(raw) {
    if (state.paused) return;
    try {
      updateUi(normalizePacket(raw));
    } catch (err) {
      setPill(els.dataState, "bad packet", "err");
    }
  }

  function connectWs() {
    if (location.protocol === "file:") {
      setPill(els.wsState, "offline preview", "warn");
      return;
    }
    if (state.ws) {
      try { state.ws.close(); } catch (err) {}
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    state.ws = ws;
    setPill(els.wsState, "WS connecting", "warn");
    ws.onopen = () => {
      stopPolling();
      setPill(els.wsState, "WS connected", "");
    };
    ws.onerror = () => setPill(els.wsState, "WS error", "err");
    ws.onclose = () => {
      setPill(els.wsState, "WS disconnected", "err");
      startPolling();
      setTimeout(connectWs, 1500);
    };
    ws.onmessage = (event) => {
      if (state.mock) return;
      try {
        handlePacket(JSON.parse(event.data));
      } catch (err) {
        setPill(els.dataState, "parse error", "err");
      }
    };
  }

  async function fetchLatest() {
    try {
      const response = await fetch("/api/imu/latest", { cache: "no-store" });
      const data = await response.json();
      if (data && data.status !== "no_data") handlePacket(data);
    } catch (err) {}
  }

  function startPolling() {
    if (location.protocol === "file:" || state.pollTimer) return;
    state.pollTimer = setInterval(fetchLatest, 120);
  }

  function stopPolling() {
    if (!state.pollTimer) return;
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  function mockPacket() {
    const t = performance.now() / 1000;
    const roll = Math.sin(t * 1.2) * 28;
    const pitch = Math.sin(t * .84 + .8) * 16;
    const yaw = wrap180(t * 24);
    const ax = Math.sin(t * 1.4) * .45;
    const ay = 9.80665 + Math.sin(t * 1.8) * .18;
    const az = Math.sin(t * 1.1 + 1.2) * .55;
    const gx = Math.cos(t * 1.2) * 32;
    const gy = Math.sin(t * 1.6) * 18;
    const gz = 24;
    return {
      ts: Date.now(),
      server_time: Date.now() / 1000,
      dt: .05,
      angles: { roll, pitch, yaw },
      accel: { x: ax, y: ay, z: az },
      gyro: { x: gx, y: gy, z: gz },
      metrics: {
        accel_norm: Math.hypot(ax, ay, az),
        gyro_norm: Math.hypot(gx, gy, gz),
        still: false,
        near_flat: Math.abs(roll) < 2 && Math.abs(pitch) < 2,
      },
      state: { motion: "moving", still: false, near_flat: false },
    };
  }

  function drawCharts() {
    drawSeries(els.angleChart, [
      { key: "roll", color: "#ff6b6b", label: "Roll" },
      { key: "pitch", color: "#5df2a5", label: "Pitch" },
      { key: "yaw", color: "#6ea8fe", label: "Yaw" },
    ], -180, 180);
    drawSeries(els.motionChart, [
      { key: "accelNorm", color: "#ffd166", label: "Accel" },
      { key: "gyroNorm", color: "#5bd8ff", label: "Gyro" },
    ]);
  }

  function drawSeries(canvas, series, fixedMin, fixedMax) {
    const ctx = canvas.getContext("2d");
    const width = canvas.width = canvas.clientWidth * devicePixelRatio;
    const height = canvas.height = canvas.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#090f16";
    ctx.fillRect(0, 0, w, h);

    const pad = { l: 40, r: 14, t: 18, b: 28 };
    ctx.strokeStyle = "rgba(255,255,255,.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const y = pad.t + (h - pad.t - pad.b) * i / 4;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(w - pad.r, y);
      ctx.stroke();
    }

    const rows = state.history;
    if (rows.length < 2) return;
    let min = fixedMin;
    let max = fixedMax;
    if (min === undefined || max === undefined) {
      const values = rows.flatMap((row) => series.map((s) => row[s.key]));
      min = Math.min(...values, 0);
      max = Math.max(...values, 1);
      if (Math.abs(max - min) < 1) max = min + 1;
    }
    const xOf = (idx) => pad.l + (w - pad.l - pad.r) * idx / Math.max(1, rows.length - 1);
    const yOf = (value) => pad.t + (h - pad.t - pad.b) * (1 - (value - min) / (max - min));

    for (const s of series) {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      rows.forEach((row, idx) => {
        const x = xOf(idx);
        const y = yOf(row[s.key]);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    ctx.font = "12px Microsoft YaHei, sans-serif";
    series.forEach((s, idx) => {
      ctx.fillStyle = s.color;
      ctx.fillText(s.label, pad.l + idx * 72, h - 9);
    });
  }

  function exportCsv() {
    const header = "time_ms,roll,pitch,yaw,accel_norm,gyro_norm,dt_ms\n";
    const rows = state.history.map((row) => [
      Math.round(row.time),
      row.roll.toFixed(4),
      row.pitch.toFixed(4),
      row.yaw.toFixed(4),
      row.accelNorm.toFixed(4),
      row.gyroNorm.toFixed(4),
      row.dtMs.toFixed(2),
    ].join(","));
    const blob = new Blob([header + rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `imu-${new Date().toISOString().replace(/[:.]/g, "-")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  els.btnMock.onclick = () => {
    setMockMode(!state.mock);
  };
  els.btnZero.onclick = () => {
    const angles = state.latest?.angles || { roll: 0, pitch: 0, yaw: 0 };
    state.offsets = { ...angles };
  };
  els.btnPause.onclick = () => {
    state.paused = !state.paused;
    els.btnPause.classList.toggle("active", state.paused);
    els.btnPause.textContent = state.paused ? "继续" : "暂停";
  };
  els.btnClear.onclick = () => {
    state.history = [];
    drawCharts();
  };
  els.btnCsv.onclick = exportCsv;

  setInterval(() => {
    if (state.mock && !state.paused) handlePacket(mockPacket());
    if (!state.mock && performance.now() - state.lastPacketAt > 3000) {
      setPill(els.dataState, "waiting data", "warn");
    }
  }, 50);

  function setMockMode(enabled) {
    state.mock = enabled;
    els.btnMock.classList.toggle("active", state.mock);
    setPill(els.dataState, state.mock ? "mock data" : "waiting data", state.mock ? "warn" : "muted");
  }

  if (location.protocol === "file:") {
    setMockMode(true);
  }

  connectWs();
  fetchLatest();
  drawCharts();
})();
