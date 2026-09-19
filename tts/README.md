# TTS 后端

本目录是 AronaAI **所有语音合成引擎**的根。桌面客户端按 `tts.backend` 只调用其中一套；`start-all.ps1` 同样只启动一套，不要同卡双开。

当前：

| 子目录 | `tts.backend` | 默认端口 | 说明 |
|--------|---------------|----------|------|
| [`gpt-sovits/`](gpt-sovits/DEPLOY.md) | `official`（缺省） | 9880 | 官方 GPT-SoVITS `api_v2.py` |
| [`gpt-sovits-minimal/`](gpt-sovits-minimal/DEPLOY.md) | `minimal` | 8000 | GPT-SoVITS_minimal_inference PyTorch API |

以后增加其它合成接口时，在本目录下并列新子目录，并在客户端 / `start-all.ps1` 增加对应 backend 名。权重、预训练和各引擎自己的 `runtime/` **不进 git**，见各子目录 `DEPLOY.md`。
