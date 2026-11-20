# ASR and Qwen-Omni Smoke Tests

## 1. Paraformer ASR

There are two practical ways to use Paraformer:

- Local model mode: use FunASR to download/cache and run the open-source model locally. This is the default for `tools/test_asr.py`.
- Local server mode: start a FunASR server yourself, then call its OpenAI-compatible transcription endpoint with `tools/test_asr.py --mode server`.

Minimal local command:

```powershell
python tools/test_asr.py path\to\recording.wav
```

Server-mode command:

```powershell
python tools/test_asr.py path\to\recording.wav --mode server --server-url http://127.0.0.1:8000/v1/audio/transcriptions
```

Recommended local variables:

```env
PARAFORMER_MODE=local
PARAFORMER_MODEL=paraformer-zh
PARAFORMER_VAD_MODEL=fsmn-vad
PARAFORMER_PUNC_MODEL=ct-punc
```

The linked ModelScope model is open source. It does not require a DashScope API key when used locally, but it does require downloading model weights and installing FunASR dependencies.

## 2. Qwen-Omni

Qwen-Omni is called through Alibaba Cloud Model Studio / DashScope OpenAI-compatible API. It requires:

```env
DASHSCOPE_API_KEY=your_real_key
DASHSCOPE_COMPAT_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_OMNI_MODEL=qwen3.5-omni-plus
```

Minimal image+text command:

```powershell
python tools/test_omni.py path\to\image.jpg --prompt "请描述图片里的障碍物"
```

Text plus audio reply:

```powershell
python tools/test_omni.py path\to\image.jpg --prompt "请描述图片里的障碍物" --with-audio
```

The script converts a local image to a Base64 data URL, sends it with the text prompt, prints streamed text output, and optionally writes returned PCM16 audio to `outputs/qwen_omni_reply.wav`.
