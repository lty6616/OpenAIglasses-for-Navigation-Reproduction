# Test Matrix

Use this matrix during weekly integration. Add dated rows below each section.

## Environment

| Date | Owner | Command | Expected | Actual | Pass | Notes |
|---|---|---|---|---|---|---|
|  | B | `python tools/check_env.py` | modules and CUDA visible |  |  |  |
|  | B | `python tools/check_models.py --load` | all models load |  |  |  |

## Server

| Date | Owner | Command | Expected | Actual | Pass | Notes |
|---|---|---|---|---|---|---|
|  | B | `python app_main.py` | server starts on 8081 |  |  |  |
|  | C | browser `/api/health` | `OK` |  |  |  |

## Video

| Date | Owner | Test | Expected | Actual | Pass | Notes |
|---|---|---|---|---|---|---|
|  | B/C | simulated `/ws/camera` | viewer shows frames |  |  |  |
|  | A/B | ESP32 camera | viewer shows live image |  |  |  |
|  | A/B | 15-minute run | no reconnect loop |  |  |  |

## Vision

| Date | Owner | Mode | Input | Expected | Actual | Pass | Failure Cause |
|---|---|---|---|---|---|---|---|
|  | B | blindpath | image/video | mask + guidance |  |  |  |
|  | B | traffic | red/green image | stable color |  |  |  |
|  | B/C | shopping | desktop item | detection + hand guidance |  |  |  |

## Audio And Voice

| Date | Owner | Test | Expected | Actual | Pass | Notes |
|---|---|---|---|---|---|---|
|  | C | `python tools/check_audio_assets.py` | no missing voice files |  |  |  |
|  | C/A | `/ws_audio` START | ASR starts or key error is explicit |  |  |  |
|  | C/A | `/stream.wav` | speaker plays prerecorded voice |  |  |  |

## Full Integration

| Date | Owner | Scenario | Expected | Actual | Pass | Notes |
|---|---|---|---|---|---|---|
|  | All | "开始导航" | state `BLINDPATH_NAV` |  |  |  |
|  | All | "检测红绿灯" | traffic mode |  |  |  |
|  | All | "找一下矿泉水" | item search mode |  |  |  |
|  | All | 30-minute run | no crash |  |  |  |
