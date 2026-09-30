<div align="center">

# video2subtitle

**自托管的视频转字幕工具。**
**浏览器里拖个视频进去（或一条命令），出来 SRT / VTT / ASS / TXT 字幕。**

[快速开始](#快速开始docker--推荐) · [English](README.md) · [产品定义](PRODUCT.md)

![status](https://img.shields.io/badge/status-v0.1.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) ![python](https://img.shields.io/badge/python-3.10%2B-informational)

多引擎语音识别（Qwen3-ASR · SenseVoice）· CPU 友好无需显卡 · 视频不出你的机器

</div>

---

## 为什么做这个

- **默认私有**——自托管，视频只进你自己的服务器，不出内网
- **一条命令跑起来**——`docker compose up`，浏览器打开，拖视频，下字幕
- **多引擎**——[Qwen3-ASR 0.6B](https://github.com/QwenLM/Qwen3-ASR)（质量优先，30 种语言 + 中文方言）与 [SenseVoice-Small](https://github.com/FunAudioLLM/SenseVoice)（速度优先）同一套引擎接口，改个环境变量就切换
- **URL 直接转**——贴一个公开视频地址，通用 yt-dlp 层负责下载（没有任何站点特化逻辑）
- **出的是真能用的字幕**——基于 token 时间戳的切句 + 静音吸附分块：断句自然、数字规整（ITN），支持 SRT/VTT/ASS/TXT
- **零构建链**——Web UI 是单文件静态页，由 API 服务直接托管

## 快速开始（Docker · 推荐）

需要 Docker + Compose v2。

```bash
git clone https://github.com/trtyr/video2subtitle
cd video2subtitle
echo "V2S_TOKEN=change-me" > .env
docker compose up -d
```

打开 **http://localhost:8765**，填入同一个 token，拖视频进去，下字幕。

不想 clone 仓库也可以直接 `docker pull ghcr.io/trtyr/video2subtitle:latest`（镜像含
`linux/amd64` + `linux/arm64` 双架构）。

> 首次启动会自动下载模型——默认 Qwen3-ASR 约 950MB；在 `.env` 里设
> `V2S_ENGINE=sensevoice` 可换约 240MB 的 SenseVoice（快约 6 倍，质量略低）。
> 模型缓存在 `./models/`。GitHub 访问慢就在 `.env` 加
> `V2S_GH_MIRROR=https://ghfast.top/`。

## 快速开始（pip / CLI）

需要 Python 3.10+ 和 PATH 里的 `ffmpeg`。

```bash
pip install -e .
export V2S_TOKEN=change-me
python -m video2subtitle.main        # 服务 + Web UI，监听 8765
```

CLI——本地文件或公开 URL 进，字幕文件出：

```bash
video2subtitle talk.mp4                          # -> talk.srt（本地引擎）
video2subtitle talk.mp4 -f vtt -o out.vtt        # 指定格式
video2subtitle https://example.com/video.mp4     # 通用 URL，走 yt-dlp
video2subtitle talk.mp4 --server http://box:8765 --token SECRET
                                                 # 用远程服务，本地不装模型
```

## 性能基准（实测，非估算）

AMD Ryzen 7 5800H · 8 onnxruntime 线程 · 真实 HTTP 全流程 · edge-tts 朗读音频（中 201.8s / 英 197.3s）：

| 引擎 | 音频 | 时长 | 推理 | RTF | 分段数 |
|---|---|---|---|---|---|
| Qwen3-ASR 0.6B int8 | 中文 | 201.8s | 37.5s | **0.186** | 14 |
| Qwen3-ASR 0.6B int8 | 英文 | 197.3s | 42.8s | **0.217** | 14 |
| SenseVoice-Small int8 | 中文 | 201.8s | 5.7s | **0.028** | 29 |
| SenseVoice-Small int8 | 英文 | 197.3s | 5.8s | **0.030** | 17 |

18 分钟视频 ⇒ **约 3.4 分钟**（Qwen3-ASR）或 **约 31 秒**（SenseVoice）。英文质量备注：SenseVoice 把 "Tonight" 听成 "Toight"、标点毛糙；Qwen3-ASR 标点完整、断句自然。

## API

交互式文档在 `/docs`（OpenAPI）。核心端点：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/transcripts` | 上传音视频（multipart `file`）→ `202 {task_id, state, queue_position}` |
| GET | `/v1/transcripts/{id}` | 状态（`queued→processing→completed/failed`）、`progress`、`result` |
| DELETE | `/v1/transcripts/{id}` | 删除任务与结果 |
| GET | `/healthz` | 版本、当前引擎、各引擎模型就绪状态、队列深度 |

结果结构：

```json
{"lang": "zh", "text": "…",
 "segments": [{"start": 0.18, "end": 4.14, "text": "…"}],
 "srt": "1\n00:00:00,180 --> 00:00:04,140\n…\n"}
```

错误双层：HTTP 状态码 + `{"error": {"code", "message"}}`，稳定错误码
（`invalid_audio`、`model_not_ready`、`queue_timeout`、`inference_failed` 等）。

## 架构

```
浏览器（拖拽）        ─┐
CLI（文件 / URL）     ─┼─▶ REST API ─▶ 串行队列 ─▶ 引擎（模型常驻）
第三方脚本            ─┘   Bearer 鉴权   任务落盘     ├─ qwen3-asr（默认）
                          ffmpeg 探测/归一化          └─ sensevoice（快速）
                                ▲                  token 时间戳切句
                                └── SRT / VTT / ASS / TXT 输出
```

串行队列是刻意的：单用户自托管场景一次跑一个推理；任务与结果落盘，重启不丢，
客户端断连后可稍后取结果。结果默认保留 7 天（可配）。

## 配置（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `V2S_TOKEN` | —（必填） | API 的 Bearer token |
| `V2S_ENGINE` | `qwen3` | `qwen3` 或 `sensevoice` |
| `V2S_HOST` / `V2S_PORT` | `127.0.0.1` / `8765` | 监听地址；**生产请绑 tailnet/内网 IP** |
| `V2S_QWEN3_MODEL_DIR` / `V2S_SENSEVOICE_MODEL_DIR` | `~/.local/share/video2subtitle/models/…` | 复用已有模型文件 |
| `V2S_AUTO_DOWNLOAD` | `1` | 离线环境设 `0` |
| `V2S_GH_MIRROR` | — | 模型下载前缀镜像，如 `https://ghfast.top/` |
| `V2S_HOTWORDS` | — | Qwen3-ASR 热词（逗号分隔） |
| `V2S_MAX_UPLOAD_MB` / `V2S_MAX_DURATION_S` | `100` / `7200` | 限制 |

## Roadmap

- [ ] v0.2：faster-whisper 引擎 · GPU（CUDA）推理
- [ ] v0.3：翻译 / 双语字幕 · ASS 样式模板
- [ ] 远期：多用户鉴权、浏览器内精修字幕

## License

[MIT](LICENSE)
