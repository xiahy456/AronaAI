"""
模型加载模块 - 支持 HF+PEFT 与 GGUF（llama-cpp-python）双后端
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from backend.config import MODEL_CONFIG


def _strip_think_blocks(text: str) -> str:
    """去掉 Qwen3 可能残留的思考块。"""
    if not text:
        return text
    if "</think>" in text:
        text = text.split("</think>")[-1]
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


class ModelLoader:
    """模型加载器，单例模式。"""

    _instance = None
    _model = None
    _tokenizer = None
    _backend: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def backend(self) -> str:
        return str(MODEL_CONFIG.get("backend", "hf")).lower()

    def load(self):
        """加载模型（懒加载）。GGUF 返回 (llama, None)；HF 返回 (model, tokenizer)。"""
        if self._model is not None and self._backend == self.backend:
            return self._model, self._tokenizer

        # 后端切换时清空缓存
        self._model = None
        self._tokenizer = None
        self._backend = self.backend

        if self._backend == "gguf":
            return self._load_gguf()
        return self._load_hf()

    def _load_gguf(self) -> Tuple[Any, None]:
        gguf_path = MODEL_CONFIG.get("gguf_path")
        if not gguf_path:
            raise ValueError("MODEL_CONFIG['gguf_path'] 未配置")

        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise ImportError(
                "未安装 llama-cpp-python。请执行: pip install llama-cpp-python\n"
                "GPU 版可参考: https://github.com/abetlen/llama-cpp-python#installation-with-hardware-acceleration"
            ) from e

        n_ctx = int(MODEL_CONFIG.get("n_ctx", 2048))
        n_gpu_layers = int(MODEL_CONFIG.get("n_gpu_layers", -1))
        print(f"正在加载 GGUF: {gguf_path}")
        print(f"  n_ctx={n_ctx}, n_gpu_layers={n_gpu_layers}")

        # chat_format=None：优先使用 GGUF 内嵌 chat template（Qwen3）
        self._model = Llama(
            model_path=str(gguf_path),
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        self._tokenizer = None
        print("GGUF 模型加载完成")
        return self._model, self._tokenizer

    def _load_hf(self) -> Tuple[Any, Any]:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print("正在加载基础模型和tokenizer（HF）...")

        self._tokenizer = AutoTokenizer.from_pretrained(
            MODEL_CONFIG["base_model_name"],
            trust_remote_code=True,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        dtype = (
            torch.float16
            if MODEL_CONFIG["torch_dtype"] == "float16"
            else torch.float32
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            MODEL_CONFIG["base_model_name"],
            torch_dtype=dtype,
            device_map=MODEL_CONFIG["device_map"],
            trust_remote_code=True,
        )

        if MODEL_CONFIG.get("lora_path"):
            print(f"正在加载LoRA权重: {MODEL_CONFIG['lora_path']}")
            self._model = PeftModel.from_pretrained(
                self._model, MODEL_CONFIG["lora_path"]
            )
            self._model.eval()

        print("模型加载完成")
        return self._model, self._tokenizer

    def generate(self, messages: list, enable_thinking: bool = False) -> str:
        """
        生成回复

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            enable_thinking: 是否启用思考过程（仅 HF/Qwen 模板；GGUF 侧强制关闭）

        Returns:
            生成的回复文本
        """
        if self.backend == "gguf":
            return self._generate_gguf(messages)
        return self._generate_hf(messages, enable_thinking=enable_thinking)

    def _generate_gguf(self, messages: List[dict]) -> str:
        llama, _ = self.load()

        # 角色扮演关闭思考；在 system 末尾再强调一次
        chat_messages = [dict(m) for m in messages]
        anti_think = "不要输出思考过程或 <think> 标签，直接回答。"
        if chat_messages and chat_messages[0].get("role") == "system":
            content = chat_messages[0].get("content") or ""
            if "<think>" not in content and "思考过程" not in content:
                chat_messages[0]["content"] = f"{content}\n{anti_think}".strip()
        else:
            chat_messages.insert(0, {"role": "system", "content": anti_think})

        result = llama.create_chat_completion(
            messages=chat_messages,
            max_tokens=int(MODEL_CONFIG.get("max_new_tokens", 128)),
            temperature=float(MODEL_CONFIG.get("temperature", 0.6)),
            top_p=float(MODEL_CONFIG.get("top_p", 0.85)),
            top_k=int(MODEL_CONFIG.get("top_k", 50)),
            repeat_penalty=float(MODEL_CONFIG.get("repetition_penalty", 1.1)),
        )
        choice = result["choices"][0]
        message = choice.get("message") or {}
        response = (message.get("content") or choice.get("text") or "").strip()
        response = _strip_think_blocks(response)
        response = response.removeprefix("<answer>\n").removeprefix("<answer>")
        return response.strip()

    def _generate_hf(self, messages: list, enable_thinking: bool = False) -> str:
        import torch

        model, tokenizer = self.load()

        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=MODEL_CONFIG["max_length"],
        ).to(model.device)

        if "token_type_ids" in inputs:
            inputs.pop("token_type_ids")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MODEL_CONFIG["max_new_tokens"],
                do_sample=True,
                temperature=MODEL_CONFIG["temperature"],
                top_p=MODEL_CONFIG["top_p"],
                top_k=MODEL_CONFIG["top_k"],
                repetition_penalty=MODEL_CONFIG["repetition_penalty"],
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        response = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1] :],
            skip_special_tokens=True,
        )
        response = _strip_think_blocks(response)
        response = response.removeprefix("<answer>\n").removeprefix("<answer>")
        return response.strip()

    def generate_with_context(
        self,
        user_input: str,
        context: str = "",
        history: list = None,
        system_prompt: str = "",
    ) -> str:
        """
        带上下文的生成

        Args:
            user_input: 用户输入
            context: RAG检索到的上下文
            history: 历史对话列表
            system_prompt: 系统提示词

        Returns:
            生成的回复
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if context:
            context_message = f"以下是相关的参考信息：\n{context}"
            messages.append({"role": "system", "content": context_message})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_input})

        return self.generate(messages)
