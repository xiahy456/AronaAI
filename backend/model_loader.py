"""
模型加载模块 - 负责加载基础模型和LoRA权重
"""
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from backend.config import MODEL_CONFIG


class ModelLoader:
    """模型加载器，单例模式"""

    _instance = None
    _model = None
    _tokenizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self):
        """加载模型和tokenizer（懒加载）"""
        if self._model is not None and self._tokenizer is not None:
            return self._model, self._tokenizer

        print("正在加载基础模型和tokenizer...")

        # 加载tokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(
            MODEL_CONFIG["base_model_name"],
            trust_remote_code=True
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        # 加载基础模型
        dtype = torch.float16 if MODEL_CONFIG["torch_dtype"] == "float16" else torch.float32
        self._model = AutoModelForCausalLM.from_pretrained(
            MODEL_CONFIG["base_model_name"],
            torch_dtype=dtype,
            device_map=MODEL_CONFIG["device_map"],
            trust_remote_code=True
        )

        # 加载LoRA权重
        if MODEL_CONFIG.get("lora_path"):
            print(f"正在加载LoRA权重: {MODEL_CONFIG['lora_path']}")
            self._model = PeftModel.from_pretrained(self._model, MODEL_CONFIG["lora_path"])
            self._model.eval()

        print("模型加载完成")
        return self._model, self._tokenizer

    def generate(self, messages: list, enable_thinking: bool = False) -> str:
        """
        生成回复

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            enable_thinking: 是否启用思考过程

        Returns:
            生成的回复文本
        """
        model, tokenizer = self.load()

        # 应用聊天模板
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking
        )

        # 编码
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=MODEL_CONFIG["max_length"]
        ).to(model.device)

        # 移除模型不支持的参数（如 token_type_ids）
        if "token_type_ids" in inputs:
            inputs.pop("token_type_ids")

        # 生成
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
                eos_token_id=tokenizer.eos_token_id
            )

        # 解码
        response = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        )

        # 去除可能的<answer>标签
        response = response.removeprefix("<answer>\n")
        response = response.removeprefix("<answer>")

        return response.strip()

    def generate_with_context(self, user_input: str, context: str = "",
                               history: list = None, system_prompt: str = "") -> str:
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

        # 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加上下文信息
        if context:
            context_message = f"以下是相关的参考信息：\n{context}"
            messages.append({"role": "system", "content": context_message})

        # 添加历史对话
        if history:
            messages.extend(history)

        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})

        return self.generate(messages)
