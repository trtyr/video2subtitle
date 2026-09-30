# video2subtitle — 产品定义

> 自托管的「视频进，字幕出」工具：任何本地视频/音频文件或公开视频 URL，转出可用的字幕文件。
> 命名拍板：video2subtitle（2026-09-30，用户定）

## 产品形态（双形态，同一引擎核心）

- **Web**（自托管服务）：浏览器拖拽上传 → 实时进度 → 字幕预览 → 多格式下载；`docker-compose up` 一键部署
- **CLI**：一条命令，本地文件或 URL → SRT/VTT/ASS/TXT
- **API**：REST（提交/轮询/结果/删除），可被第三方当转写后端集成（OpenAPI 文档随服务提供）

## v0.1.0 功能范围

| 维度 | 内容 |
|---|---|
| 转写引擎 | Qwen3-ASR 0.6B int8（默认）/ SenseVoice-Small int8（兜底），env 一行切换；首次启动自动下载模型 |
| 输入 | 本地视频/音频文件（ffmpeg 支持的常见容器/编码）；公开视频 URL（yt-dlp 通用实现，**无任何站点特化**） |
| 输出格式 | SRT / VTT / ASS / TXT |
| Web UI | 拖拽上传、实时进度（含排队位）、字幕预览、多格式下载；零构建链静态页（服务直接托管） |
| API | `POST /v1/transcripts`（202 + task_id）、`GET /v1/transcripts/{id}`（progress/queue_position/result）、`DELETE`、`GET /healthz`；双层错误码 |
| 安全 | Bearer token 鉴权；默认只绑本机/tailnet，不对公网暴露 |
| 部署 | docker-compose（server + web 同容器）；ghcr 公开镜像 |

如实标注的限制：串行队列单并发；Web 上传 ≤100MB；音频时长 ≤2h；任务与结果落盘保留 7 天。

## v0.2+ roadmap（明确不进 v0.1）

1. faster-whisper 引擎（多语种通用，国际社区刚需）
2. GPU（CUDA）推理
3. 翻译 / 双语字幕
4. ASS 样式增强（字体/位置模板）
5. API 多用户与鉴权增强

## Non-goals

- B 站等特定站点的登录态/专属下载逻辑（只保留 yt-dlp 通用层）
- 公开 SaaS 服务

## 性能基准（AMD Ryzen 7 5800H · 8 onnxruntime 线程 · 实测）

| 引擎 | 音频 | 时长 | 推理 | RTF |
|---|---|---|---|---|
| Qwen3-ASR 0.6B int8 | 中文 | 201.8s | 37.5s | 0.186 |
| Qwen3-ASR 0.6B int8 | 英文 | 197.3s | 42.8s | 0.217 |
| SenseVoice-Small int8 | 中文 | 201.8s | 5.7s | 0.028 |
| SenseVoice-Small int8 | 英文 | 197.3s | 5.8s | 0.030 |

18 分钟视频 ≈ 3.4 分钟（Qwen3）/ 31 秒（SenseVoice）。

## 架构原则

- 引擎抽象层（Engine protocol）：换引擎 = 新增一个实现文件，API/UI 零改动
- 零构建链：Web UI 为内嵌静态页，不引入 Node 构建依赖
- 任务与结果落盘：服务重启不丢已完成结果
