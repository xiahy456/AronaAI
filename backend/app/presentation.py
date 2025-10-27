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

#函数名: receiveMessage
#参数:
#   null
#返回值:
#   str 用户输入的字符串
#作用： 
#   从前端获取用户输入
def receiveMessage():
    user_input = input("请输入你想对阿罗娜说的话，输入\'exit\'结束对话:\n")
    return user_input

#函数名: presentationHandle
#参数:
#   null
#返回值:
#   null
#作用： 
#   接收来自receivedMessage()的用户输入的信息，交给下一层处理
def presentationHandle():
    continueInteract = True
    while (continueInteract): 
        user_input = receiveMessage()
        if user_input=="exit": 
            break
        print(user_input)
        print("")
    print(f"对话结束")