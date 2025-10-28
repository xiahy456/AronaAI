# Copyright xia_hy456. All rights reserved.

# @Author: xia_hy456
# @Date: 2025/10/27 08:52:16

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
from .LLM import LLM
from .CoreAbilities import CoreAbilities

# DialogueManager层，用于组装上下文并送给LLM层、DAO层
class DialogueManager:

    # dialogueManagerHandle
    # 参数:
    #   str 用户接收的消息
    # 返回值:
    #   str LLM层返回的消息
    # 作用： 
    #   接收来自Presentation层的消息，通过CoreAbilities层组装上下文，交给LLM层
    #   同时进行数据持久化处理，最后将LLM层返回的信息返还给Presentation层
    @classmethod
    def dialogueManagerHandle(cls, user_input):
        # 调取CoreAbilities内容，组装上下文
        complete_message = CoreAbilities.coreAbilitiesHandle(user_input)

        # 将组装得到的信息交给LLM层
        return_message = LLM.lLMHandle(complete_message)
        # 进行数据持久化处理

        # 将最后得到的信息return给Presentation
        return return_message