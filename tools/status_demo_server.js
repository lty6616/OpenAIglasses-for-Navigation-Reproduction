#!/usr/bin/env node
'use strict';

// Dependency-free /status integration server. It mirrors the production HTTP and
// WebSocket contracts so the frontend can be demonstrated before AI dependencies load.
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const path = require('path');
const dgram = require('dgram');

const projectRoot = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const host = option('--host', '127.0.0.1');
const port = Number(option('--port', '8081'));
const udpPort = Number(option('--udp-port', '12345'));
const fps = Math.max(0, Number(option('--fps', '5')));
const imagePath = path.resolve(option('--image', path.join(projectRoot, 'static', 'status_demo.jpg')));
const startedAt = Date.now();

const viewers = new Set();
const uiClients = new Set();
const imuClients = new Set();
const sockets = new Set();
let cameraClient = null;
let audioClient = null;
let lastFrameAt = 0;
let lastImuAt = 0;
let demoFrame = null;
const cameraFreshMs = 5000;

function cameraIsFresh(now = Date.now()) {
  return cameraClient !== null && lastFrameAt > 0 && now - lastFrameAt <= cameraFreshMs;
}

function dropStaleCamera(now = Date.now()) {
  if (cameraClient && lastFrameAt > 0 && now - lastFrameAt > cameraFreshMs) {
    const stale = cameraClient;
    cameraClient = null;
    stale.destroy();
  }
}

function sendHttp(res, status, type, body) {
  res.writeHead(status, {
    'Content-Type': type,
    'Cache-Control': 'no-store',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

function serveFile(res, relative, type) {
  const file = path.join(projectRoot, relative);
  fs.readFile(file, (err, data) => {
    if (err) return sendHttp(res, 404, 'text/plain; charset=utf-8', 'Not found');
    sendHttp(res, 200, type, data);
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  if (url.pathname === '/' || url.pathname === '/status') {
    return serveFile(res, path.join('templates', 'status.html'), 'text/html; charset=utf-8');
  }
  if (url.pathname === '/static/status.css') {
    return serveFile(res, path.join('static', 'status.css'), 'text/css; charset=utf-8');
  }
  if (url.pathname === '/static/status.js') {
    return serveFile(res, path.join('static', 'status.js'), 'text/javascript; charset=utf-8');
  }
  if (url.pathname === '/api/health') {
    return sendHttp(res, 200, 'text/plain; charset=utf-8', 'OK');
  }
  if (url.pathname === '/api/status') {
    const now = Date.now();
    dropStaleCamera(now);
    const data = {
      server_time: now / 1000,
      uptime_sec: Math.round((now - startedAt) / 100) / 10,
      camera_esp32_connected: cameraIsFresh(now),
      demo_stream_active: demoFrame !== null && !cameraIsFresh(now),
      audio_esp32_connected: audioClient !== null,
      viewer_count: viewers.size,
      ui_client_count: uiClients.size,
      imu_client_count: imuClients.size,
      last_frame_age_ms: lastFrameAt ? now - lastFrameAt : null,
      last_imu_age_ms: lastImuAt ? now - lastImuAt : null,
      navigation_active: false,
      yolomedia_running: false,
    };
    return sendHttp(res, 200, 'application/json; charset=utf-8', JSON.stringify(data));
  }
  sendHttp(res, 404, 'text/plain; charset=utf-8', 'Not found');
});

function frame(opcode, payload) {
  const data = Buffer.isBuffer(payload) ? payload : Buffer.from(payload);
  let head;
  if (data.length < 126) {
    head = Buffer.from([0x80 | opcode, data.length]);
  } else if (data.length < 65536) {
    head = Buffer.alloc(4);
    head[0] = 0x80 | opcode;
    head[1] = 126;
    head.writeUInt16BE(data.length, 2);
  } else {
    head = Buffer.alloc(10);
    head[0] = 0x80 | opcode;
    head[1] = 127;
    head.writeBigUInt64BE(BigInt(data.length), 2);
  }
  return Buffer.concat([head, data]);
}

function send(socket, opcode, payload) {
  if (!socket.destroyed && socket.writable) socket.write(frame(opcode, payload));
}

function broadcast(clients, opcode, payload) {
  for (const socket of clients) send(socket, opcode, payload);
}

function attachParser(socket, onMessage) {
  let buffer = Buffer.alloc(0);
  socket.on('data', (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    while (buffer.length >= 2) {
      const opcode = buffer[0] & 0x0f;
      const masked = Boolean(buffer[1] & 0x80);
      let length = buffer[1] & 0x7f;
      let offset = 2;
      if (length === 126) {
        if (buffer.length < 4) return;
        length = buffer.readUInt16BE(2);
        offset = 4;
      } else if (length === 127) {
        if (buffer.length < 10) return;
        length = Number(buffer.readBigUInt64BE(2));
        offset = 10;
      }
      const maskOffset = offset;
      if (masked) offset += 4;
      if (buffer.length < offset + length) return;
      const payload = Buffer.from(buffer.subarray(offset, offset + length));
      if (masked) {
        const mask = buffer.subarray(maskOffset, maskOffset + 4);
        for (let i = 0; i < payload.length; i += 1) payload[i] ^= mask[i % 4];
      }
      buffer = buffer.subarray(offset + length);
      if (opcode === 0x8) return socket.end(frame(0x8, payload));
      if (opcode === 0x9) send(socket, 0xA, payload);
      else if (opcode === 0x1 || opcode === 0x2) onMessage(opcode, payload);
    }
  });
}

function acceptUpgrade(req, socket) {
  const key = req.headers['sec-websocket-key'];
  if (!key) return socket.destroy();
  const accept = crypto.createHash('sha1')
    .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
    .digest('base64');
  socket.write([
    'HTTP/1.1 101 Switching Protocols',
    'Upgrade: websocket',
    'Connection: Upgrade',
    `Sec-WebSocket-Accept: ${accept}`,
    '', '',
  ].join('\r\n'));
}

server.on('upgrade', (req, socket) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (!['/ws/camera', '/ws/viewer', '/ws_audio', '/ws_ui', '/ws'].includes(pathname)) {
    return socket.destroy();
  }
  if (pathname === '/ws/camera') {
    dropStaleCamera();
    if (cameraClient) return socket.destroy();
  }
  acceptUpgrade(req, socket);
  socket.setKeepAlive(true, 5000);
  socket.setNoDelay(true);
  sockets.add(socket);

  let group = null;
  if (pathname === '/ws/viewer') group = viewers;
  if (pathname === '/ws_ui') group = uiClients;
  if (pathname === '/ws') group = imuClients;
  if (group) group.add(socket);
  if (pathname === '/ws/camera') {
    cameraClient = socket;
    lastFrameAt = Date.now();
  }
  if (pathname === '/ws_audio') audioClient = socket;

  if (pathname === '/ws_ui') {
    send(socket, 0x1, `INIT:${JSON.stringify({ partial: '', finals: ['[系统] 状态页联调服务已启动'] })}`);
  }
  attachParser(socket, (opcode, payload) => {
    if (pathname === '/ws/camera' && opcode === 0x2) {
      lastFrameAt = Date.now();
      broadcast(viewers, 0x2, payload);
    }
    if (pathname === '/ws_audio' && opcode === 0x1) {
      const text = payload.toString('utf8');
      if (text.startsWith('PROMPT:')) broadcast(uiClients, 0x1, `FINAL:${text.slice(7)}`);
    }
  });
  const cleanup = () => {
    sockets.delete(socket);
    if (group) group.delete(socket);
    if (cameraClient === socket) cameraClient = null;
    if (audioClient === socket) audioClient = null;
  };
  socket.on('close', cleanup);
  socket.on('error', cleanup);
});

const udp = dgram.createSocket('udp4');
udp.on('message', (message) => {
  try {
    JSON.parse(message.toString('utf8'));
    lastImuAt = Date.now();
    broadcast(imuClients, 0x1, message);
  } catch (_) { /* ignore malformed UDP packets */ }
});
udp.bind(udpPort, host);

if (fps > 0 && fs.existsSync(imagePath)) {
  demoFrame = fs.readFileSync(imagePath);
  setInterval(() => {
    dropStaleCamera();
    if (cameraIsFresh()) return;
    lastFrameAt = Date.now();
    broadcast(viewers, 0x2, demoFrame);
  }, Math.round(1000 / fps));
}

server.listen(port, host, () => {
  console.log(`[STATUS DEMO] http://${host}:${port}/status`);
  console.log(`[STATUS DEMO] UDP IMU ${host}:${udpPort}`);
  console.log(demoFrame ? `[STATUS DEMO] mock camera ${fps} FPS` : '[STATUS DEMO] waiting for /ws/camera');
});

function shutdown() {
  for (const socket of sockets) socket.destroy();
  udp.close();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1000).unref();
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
