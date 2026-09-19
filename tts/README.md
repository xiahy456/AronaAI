# TTS 后端

本目录是 AronaAI **所有语音合成引擎**的根。桌面客户端按 `tts.backend` 只调用其中一套；`start-all.ps1` 同样只启动一套。**不要同卡双开**官方与 minimal。

| 子目录 | `tts.backend` | 默认端口 | 适用 |
|--------|---------------|----------|------|
| [`gpt-sovits/`](gpt-sovits/DEPLOY.md) | `official`（缺省） | 9880 | 官方整合包 `api_v2.py`，兼容现有 `/tts` |
| [`gpt-sovits-minimal/`](gpt-sovits-minimal/DEPLOY.md) | `minimal` | 8000 | [GPT-SoVITS_minimal_inference](https://github.com/GPT-SoVITS-Devel/GPT-SoVITS_minimal_inference) 的 PyTorch API，首包更快；**复用**官方目录里的权重与 BERT/HuBERT |

权重、预训练、各引擎 `runtime/` 和上游 clone **不进 git**。本仓库只跟踪启动脚本、文档、`launch_api.py`、`voices.json` 和参考音频。

---

## 选哪套

- **日常桌宠、先求能出声**：用 `official`。Windows 整合包自带 Python，步骤最少。
- **要更低首包延迟**：用 `minimal`。必须有本目录 `runtime\python.exe`（发布包已带，或本地 `pack-runtime.ps1` 打出），并且 clone 了上游 `api_server.py`。权重仍只放在 `gpt-sovits/`，不要复制一份。

客户端 `Config/config.json`：

```json
"tts": {
  "backend": "official",
  "host": "127.0.0.1",
  "port": 9880,
  "minimal_host": "127.0.0.1",
  "minimal_port": 8000,
  "voice": "arona"
}
```

`backend` 改成 `minimal` 后走 `minimal_host` / `minimal_port`。`start-all.ps1` 读同一份配置，只拉起对应进程。也可用 `.\start-all.ps1 -TtsBackend minimal` 临时覆盖。

---

## Windows 推荐部署（终端用户）

需要：**NVIDIA GPU**（建议 ≥ 8 GB 显存）、[VC++ x64 运行库](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)、能跑 CUDA 12.6 的驱动。

### 1. 解压本仓库的 TTS 发布包

从 [Releases](https://github.com/xiahy456/AronaAI/releases) 下载 `AronaAI_GPTSoVITS_v*_x64.zip`，**解压到仓库根目录**（与 `start-all.ps1` 同级），使存在：

```
tts/README.md
tts/gpt-sovits/go-apiv2.bat
tts/gpt-sovits/ref_audio/Arona/*.ogg
tts/gpt-sovits-minimal/launch_api.py
tts/gpt-sovits-minimal/runtime/python.exe
```

这个 zip **不含**官方整合包、不含阿洛娜 ckpt、也不含 minimal 上游源码。维护者本地可用 `.\pack-tts.ps1` 打出同样布局的包。

### 2. 放入官方 GPT-SoVITS（两套都需要）

minimal 也要读这里的预训练和权重，所以这一步不能省。

1. 下载 [官方 Windows 整合包](https://huggingface.co/lj1995/GPT-SoVITS-windows-package)（国内可用[语雀镜像](https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4#KTvnO)）。
2. 把包内文件解压进 `tts/gpt-sovits/`，使存在 `tts/gpt-sovits/api_v2.py` 和 `GPT_SoVITS/pretrained_models/chinese-hubert-base`、`chinese-roberta-wwm-ext-large`。
3. **不要覆盖**已有的 `DEPLOY.md`、`go-apiv2.*`、`watch-apiv2.*`、`ref_audio/`。

### 3. 放入阿洛娜 v2 权重

放到官方工作目录（路径相对 `tts/gpt-sovits/`）：

```
tts/gpt-sovits/GPT_weights_v2/ALuoNa_cn-e15.ckpt
tts/gpt-sovits/SoVITS_weights_v2/ALuoNa_cn_e16_s256.pth
```

不要放进仓库根 `models/`。参考音频已在发布包的 `ref_audio/Arona/`。

### 4a. 只跑官方

客户端 `tts.backend` 保持缺省 / `"official"`。仓库根执行：

```powershell
.\start-all.ps1
```

或只启动 TTS：`cd tts\gpt-sovits` 后运行 `go-apiv2.bat`。默认 `127.0.0.1:9880`。横幅里官方 Python 应是 `tts\gpt-sovits\runtime\python.exe`（整合包自带）。细节见 [`gpt-sovits/DEPLOY.md`](gpt-sovits/DEPLOY.md)。

### 4b. 跑 minimal（加速）

1. 把 [GPT-SoVITS_minimal_inference](https://github.com/GPT-SoVITS-Devel/GPT-SoVITS_minimal_inference) clone 进 `tts/gpt-sovits-minimal/`，使存在 `api_server.py`。**不要改、不要覆盖** `launch_api.py`、`watch-api.ps1`、`DEPLOY.md`、`config/voices.json`、`go-api.*`。示例：

   ```powershell
   git clone --depth 1 https://github.com/GPT-SoVITS-Devel/GPT-SoVITS_minimal_inference.git .gpt-sovits-minimal-upstream
   robocopy .gpt-sovits-minimal-upstream tts\gpt-sovits-minimal /E /XD .git /XF DEPLOY.md launch_api.py
   git checkout -- tts/gpt-sovits-minimal/config/voices.json tts/gpt-sovits-minimal/DEPLOY.md tts/gpt-sovits-minimal/watch-api.ps1 tts/gpt-sovits-minimal/launch_api.py tts/gpt-sovits-minimal/go-api.ps1 tts/gpt-sovits-minimal/go-api.bat tts/gpt-sovits-minimal/pack-runtime.ps1
   ```

2. 客户端设 `"backend": "minimal"`。**不要**再开官方 `api_v2.py`。
3. `.\start-all.ps1`。启动横幅 `TtsPython` 必须是 `tts\gpt-sovits-minimal\runtime\python.exe`，不要用官方整合包的 Python。
4. 默认 `127.0.0.1:8000`，`POST /v1/audio/speech`。

`watch-api.ps1` 会把 `pretrained_models` junction 到官方预训练目录，并经 `launch_api.py` 启动上游 API（不修改上游源码）。细节见 [`gpt-sovits-minimal/DEPLOY.md`](gpt-sovits-minimal/DEPLOY.md)。

---

## 从源码 / 维护者

仓库 clone 后这里通常只有脚本和文档，没有整合包、没有 `runtime/`、没有 `api_server.py`。

| 目的 | 命令 |
|------|------|
| 从 conda 制作 minimal 便携 Python | `tts\gpt-sovits-minimal\pack-runtime.ps1` |
| 打 Release 用的 TTS zip（脚本 + 参考音频 + minimal runtime） | 仓库根 `.\pack-tts.ps1` → `release\AronaAI_GPTSoVITS_v*_x64.zip` |
| 本机一键 | `.\start-all.ps1`（或 `-TtsBackend official\|minimal`） |

conda 环境名 `gpt-sovits-minimal` 只用于**制作** runtime，日常启动走 `runtime\python.exe`。装 CUDA Torch 时用 cu126 轮子，不要让 pip 装成 `+cpu`。官方引擎继续用整合包自带的 `tts/gpt-sovits/runtime`。

---

## 同机与异机

- **同机（默认）**：后端、TTS、客户端一台 Windows 机器，`start-all.ps1`。客户端 `tts.host` / `minimal_host` 用 `127.0.0.1`。
- **TTS 单独一台**：在该机完成上面的目录布局；官方加 `-a 0.0.0.0`，minimal 用 `watch-api.ps1 -ListenAddress 0.0.0.0`；防火墙放行 `9880` 或 `8000`；客户端填 TTS 机 IP。权重路径仍是 **TTS 机工作目录上的相对路径**。不要把 API 暴露到公网（无鉴权）。

---

## 约束

- 上游 clone 的文件不要改。阿洛娜侧只放在 `launch_api.py`、`watch-api.ps1`、`voices.json`。
- 本期 minimal 只用 PyTorch `api_server.py`，不用 ONNX / TensorRT。
- 日志在仓库根 `.start-logs/gpt-sovits.log`，不在 `tts/.start-logs`。
