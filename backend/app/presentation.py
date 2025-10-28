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
from .DialogueManager import DialogueManager

# Presentation层，用于与前端进行交互
class Presentation:

    # receiveMessage
    # 参数:
    #   null
    # 返回值:
    #   str 用户输入的字符串
    # 作用： 
    #   从前端获取用户输入
    @classmethod
    def receiveMessage(cls):
        # 获取用户输入
        user_input = input("请输入你想对阿罗娜说的话，输入\'exit\'结束对话:\n")

        # 返回给presentationHandle
        return user_input


    # presentationHandle
    # 参数:
    #   null
    # 返回值:
    #   null
    # 作用： 
    #   接收来自receivedMessage()的用户输入的信息，交给下一层处理
    @classmethod
    def presentationHandle(cls):
        while (True): 
            # 接收用户输入
            user_input = Presentation.receiveMessage()
            print("")

            # 判断是否退出
            if user_input=="exit": 
                break

            # 将信息交给DialogueManage层处理
            ai_return = DialogueManager.dialogueManagerHandle(user_input)

            # 输出DialogueManager层的返回信息
            print(f"阿罗娜:\n{ai_return}\n")

        # 退出交互循环
        print(f"对话结束")