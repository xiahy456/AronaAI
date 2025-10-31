# Copyright xia_hy456. All rights reserved.

# @Author: xia_hy456
# @Date: 2025/10/27 15:41:08

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# 包含文件
import torch
from transformers import AutoModel, AutoTokenizer
import os
from pathlib import Path

# LLM层，用于与模型进行交互
class LLM:

    _model = None
    _tokenizer = None
    _model_loaded = False

    @classmethod
    def initialize_model(cls):
        """初始化模型（单例模式）"""
        if not cls._model_loaded:
            try:
                model_path = "D:/Code/projects/Arona/arona-ai/models/chatglm3-6b"
                
                print("正在初始化 ChatGLM 模型...")
                cls._tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    trust_remote_code=True
                )
                # 使用量化
                cls._model = AutoModel.from_pretrained(
                    model_path, 
                    trust_remote_code=True
                ).quantize(4).cuda()
                
                cls._model_loaded = True
                print("ChatGLM 模型初始化完成！")
                
            except Exception as e:
                print(f"模型初始化失败: {e}")
                raise

    # LLMHandle
    # 参数
    #   str input 组装上下文完毕后的字符串
    # 返回值
    #   str 大模型返回
    # 作用
    #   将输入给到大模型，接收并返回其输出
    @classmethod
    def lLMHandle(cls, input_msg, history=None):
        # 读取历史
        if history is None:
            history = []

        # 确保模型已初始化
        if not cls._model_loaded:
            cls.initialize_model()

        # 与大模型交互
        response, updated_history = cls._model.chat(
            cls._tokenizer, 
            input_msg, 
            history=history,
            # 更多参数
            max_new_tokens=320,      # 适中的长度
            num_beams=1,
            do_sample=True,          # 启用采样获得更好质量
            temperature=0.3,         # 低随机性
            top_p=0.85,              # 适中的多样性
            repetition_penalty=1.08
        )
        
        # 返回response
        return response