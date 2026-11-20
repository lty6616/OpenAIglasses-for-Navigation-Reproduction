#pragma once

// Copy this file to config.h before flashing:
//   compile/config.example.h -> compile/config.h
// Keep config.h private because it contains WiFi credentials.

#define AIGLASS_WIFI_SSID "YOUR_WIFI_SSID"
#define AIGLASS_WIFI_PASS "YOUR_WIFI_PASSWORD"

// LAN IP of the computer running `python app_main.py`.
// The server must listen on 0.0.0.0:8081 and the firewall must allow port 8081.
#define AIGLASS_SERVER_HOST "192.168.1.100"
#define AIGLASS_SERVER_PORT 8081

// IMU UDP target. Usually the same computer as AIGLASS_SERVER_HOST.
#define AIGLASS_UDP_HOST AIGLASS_SERVER_HOST
#define AIGLASS_UDP_PORT 12345
