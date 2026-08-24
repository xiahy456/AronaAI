把本地模型权重放到本目录（相对后端便携包根目录）。

向量记忆 / 知识 RAG 需要
  bge-small-zh-v1.5/
    Hugging Face / ModelScope：BAAI/bge-small-zh-v1.5
    config.yaml → knowledge.embedding_model_path

可选：Arona-Renderer（将 model.enabled 设为 true）
  AronaLM-Renderer-V2.4/AronaLM-Renderer-V2.4.Q4_K_M.gguf
    https://www.modelscope.cn/models/xiahy456/AronaLM-Renderer-V2.4
    config.yaml → model.gguf_path

可选：本地单模型回落
  AronaLM-Generator-V2.0/AronaLM-Generator-V2.0.Q4_K_M.gguf
    https://www.modelscope.cn/models/xiahy456/AronaLM-Generator-V2.1

不要把微调基座（Qwen3-1.7B*）放这里，那些只用于训练。
完整说明见仓库 models/README.md。
