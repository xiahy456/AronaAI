# Copyright xia_hy456. All rights reserved.

# @Author: xia_hy456
# @Date: 2025/10/27 16:07:16

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Knowledge模块，用于从知识库中获取大模型需要具备的知识
class Knowledge:
    # knowledgeHandle
    # 参数
    #   null
    # 返回值
    #   str 知识字符串
    # 作用
    #   获取模型应当拥有的知识，以字符串返回
    @classmethod
    def knowledgeHandle(cls, input):
        knowledge_str = f"根据{input}联想到的知识"
        return knowledge_str