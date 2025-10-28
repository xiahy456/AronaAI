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
    def coreAbilitiesHandle(cls, input):
        final_message = input
        # 调用memory模块
        memory_message = Memory.memoryHandle(input)
        # 调用Emotion模块
        emotion_message = Emotion.emotionHandle(input)
        # 调用Knowledge模块
        knowledge_message = Knowledge.knowledgeHandle(input)
        # 调用Personality模块
        personality_message = Personality.personalityHandle()
        # 组装上下文

        # 返回final_message
        return final_message