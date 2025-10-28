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

# LLM层，用于与模型进行交互
class LLM:
    
    # LLMHandle
    # 参数
    #   str input 组装上下文完毕后的字符串
    # 返回值
    #   str 大模型返回
    # 作用
    #   将输入给到大模型，接收并返回其输出
    @classmethod
    def lLMHandle(cls, input):
        return_message = input
        
        # 返回return_message
        return return_message