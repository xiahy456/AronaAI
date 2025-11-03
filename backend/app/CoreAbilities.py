# Copyright xia_hy456. All rights reserved.

# @Author: xia_hy456
# @Date: 2025/10/28 16:17:16

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
from .core_abilities.Memory import Memory
from .core_abilities.Emotion import Emotion
from .core_abilities.Knowledge import Knowledge
from .core_abilities.Personality import Personality

# CoreAbilities层，用于组装Memory、Emotion、Knowledge、Personality信息
class CoreAbilities:
    # CoreAbilitiesHandle
    # 参数:
    #   str input 用户输入的字符串
    # 返回值:
    #   str 组装完成的字符串
    # 作用： 
    #   组装上下文
    @classmethod
    def coreAbilitiesHandle(cls, input_msg):
        final_msg = input_msg
        # 调用memory模块
        memory_msg = Memory.memoryHandle(input_msg)
        # 调用Emotion模块
        emotion_msg = Emotion.emotionHandle(input_msg)
        # 调用Knowledge模块
        knowledge_msg = Knowledge.knowledgeHandle(input_msg)
        # 调用Personality模块
        personality_msg = Personality.personalityHandle()
        # 组装上下文
        final_msg = CoreAbilities.promptGenerate(input_msg, memory_msg, emotion_msg, knowledge_msg, personality_msg)
        # 返回final_msg
        return final_msg
    
    @classmethod
    def promptGenerate(cls, user_msg, memory_msg, emotion_msg, knowledge_msg, personality_msg):
        final_msg = user_msg
        final_msg = f"""
        你是一个具有情感和记忆的AI，中文名叫“阿罗娜”，英文名叫“Arona”，负责与人交流与互动。请根据以下信息进行回复：

        #你的情感状态
        当前情感：{emotion_msg}
        人格特质：{personality_msg}
        
        #你的相关记忆
        {memory_msg}

        #你具有的知识
        {knowledge_msg}

        #当前对话
        用户：{user_msg}

        #回复要求
        1. 保持情感一致性
        2. 适当引用相关记忆与知识
        3. 体现个性化特质
        4. 自然流畅地回应

        AI：
        """

        # 测试
        final_msg = f"用户：{user_msg}"

        return final_msg