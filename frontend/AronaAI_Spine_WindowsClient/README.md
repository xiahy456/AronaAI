# AronaAI Windows 桌面客户端

基于 Qt/C++ + Spine 2D 的 Windows 桌面客户端，经 WebSocket 对接后端，可接 GPT-SoVITS TTS 与腾讯云 ASR。

## 配置说明

配置文件位于 `Config/`（由 [`Config/config.example.json`](Config/config.example.json) 复制为 `config.json`，已 gitignore）。完整示例如下：

```json
{
  "settings": {
    "frame_rate": 60, // 全局帧率
    "dict_path": "Dict/dict_zh.json", // 词典文件路径
    "zoom": 1.0, // 界面缩放比例
    "transparent": 1.0, // 主窗口整体不透明度（0.0~1.0）
    "offset_from_screen_bottom": -50, // 主窗口相对屏幕底部的向上偏移（像素）
    "offset_from_screen_left": 0, // 主窗口相对屏幕左侧的向右偏移（像素）
    "output_text_box_offset": -50, // 输出文本框相对默认位置的垂直偏移（像素；正值向上，负值向下）
    "mouse_event_transparent": true, // 是否启用鼠标穿透（点击穿透桌宠）
    "open_setting_widget": false, // 启动时是否自动打开设置窗口
    "arona_ai_mode": 0, // 阿洛娜 AI 模式：0=日程模式，1=档案模式
  },
  "aronalm": {
    "websocket_url": "ws://your.aronalm.ip:20456/ws", // AronaLM 后端 WebSocket 地址
    "heartbeat_interval": 30000, // 心跳发送间隔（毫秒）
    "heartbeat_timeout": 10000, // 心跳超时时间（毫秒）
    "reconnect_interval": 3000, // 断线重连间隔（毫秒）
    "max_reconnect_attempts": 5, // 最大重连次数
    "use_cache": true, // 是否启用响应缓存
    "use_rag": true, // 是否启用知识库 RAG 检索
    "use_memory": true // 是否启用长期记忆
  },
  "spine": {
    "skelOrJson_path": "Assets/AronaSpineAssets/arona_spr_full.json", // Spine 骨架文件（.skel / .json）路径（如果想要普拉娜可以改为Assets/AronaSpineAssets/NP0035_spr.skel）
    "atlas_path": "Assets/AronaSpineAssets/arona_spr_full.atlas", // Spine 图集 atlas 路径（如果想要普拉娜可以改为Assets/AronaSpineAssets/NP0035_spr.atlas）
    "animation_default_mix": 0.2 // 动画默认过渡混合时间（秒）
  },
  "tts": {
    "host": "your.gpt.sovits.ip", // GPT-SoVITS 服务地址
    "port": 9880, // GPT-SoVITS 服务端口
    "gpt_path": "GPT_weights_v2/ALuoNa_cn-e15.ckpt", // 推荐的 GPT 模型权重路径（服务端侧）
    "sovits_path": "SoVITS_weights_v2/ALuoNa_cn_e16_s256.pth", // 推荐的 SoVITS 模型权重路径（服务端侧）
    "ref_audio_path": "ref_audio/Arona/arona_academy_in_2.ogg", // 推荐的参考音频路径（服务端侧）
    "prompt_text": "这里为您准备了各种课程和活动，请按您喜欢的方式安排日程吧！", // 参考音频对应的提示文本
    "prompt_lang": "zh", // 提示文本语言
    "top_k": 15, // Top-K 采样
    "top_p": 1.0, // Top-P 采样
    "temperature": 1.0, // 采样温度
    "text_split_method": "cut0", // 文本分割方法
    "batch_size": 1, // 批处理大小
    "batch_threshold": 0.75, // 批处理阈值
    "split_bucket": true, // 是否按桶分割推理
    "speed_factor": 1.0, // 语速因子
    "fragment_interval": 0.3, // 片段间隔（秒）
    "seed": -1, // 随机种子（-1 表示随机）
    "parallel_infer": true, // 是否启用并行推理（8GB 显卡建议 false）
    "request_timeout_ms": 45000, // 客户端等待 /tts 的超时（毫秒）；超时后仍显示字幕，不卡死 UI
    "repetition_penalty": 1.35, // 重复惩罚系数
    "sample_steps": 32, // 采样步数
    "super_sampling": false // 是否启用超采样
  },
  "audio_input": {
    "device": "" // 音频输入设备名（空字符串表示使用系统默认设备）
  },
  "short_cut_key": {
    "switch_audio_input": "Ctrl+Alt+V", // 切换 / 触发语音输入的快捷键
    "switch_mouse_transparent": "Ctrl+Alt+C"  // 切换 / 触发鼠标穿透的快捷键
  },
  "tencent_speech_recognizer": {
    "secret_id": "${TENCENT_SECRET_ID}", // 腾讯云 SecretId（可用环境变量占位）
    "secret_key": "${TENCENT_SECRET_KEY}" // 腾讯云 SecretKey（可用环境变量占位）
  }
}
```

> **注意**：
> - 资源路径相对**程序工作目录**解析；在 Visual Studio 中调试时默认为项目根目录，请勿直接双击 `x64/Debug` 或 `x64/Release` 下的 exe（工作目录会不对）。
> - `config.json` 已在 `.gitignore` 中，不会被提交到版本控制。
> - 构建与启动步骤见仓库根目录 [`README.md`](../../README.md) 中的「客户端构建」。
