# Wiring Checklist

Use this before each firmware test.

## XIAO ESP32S3 Sense

- [ ] USB-C cable supports data, not only charging.
- [ ] Board package and selected board match XIAO ESP32S3.
- [ ] Serial monitor baud rate is `115200`.
- [ ] Camera ribbon cable is fully seated.
- [ ] Antenna/WiFi signal is stable.

## Microphone

Firmware defaults:

| Signal | Pin |
|---|---|
| PDM clock | 42 |
| PDM data | 41 |

## Speaker With MAX98357A

Firmware defaults:

| Signal | Pin |
|---|---|
| BCLK | 7 |
| LRCK | 8 |
| DIN | 9 |

Checklist:

- [ ] MAX98357A has stable power and common ground.
- [ ] Speaker impedance is suitable for the amplifier.
- [ ] `/stream.wav` is reachable from the same network.

## ICM42688 IMU Over SPI

Firmware defaults:

| Signal | Pin |
|---|---|
| SCK | 1 |
| MOSI | 2 |
| MISO | 3 |
| CS | 4 |

Checklist:

- [ ] IMU module uses the expected voltage level.
- [ ] SPI pins match `compile.ino`.
- [ ] Server UDP port `12345` is allowed through firewall.

## Network

- [ ] `compile/config.h` exists and contains local WiFi credentials.
- [ ] `AIGLASS_SERVER_HOST` is the LAN IP of the server computer.
- [ ] Server is running with `host="0.0.0.0", port=8081`.
- [ ] Windows firewall allows inbound TCP 8081 and UDP 12345.
