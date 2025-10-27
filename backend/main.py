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
from app.presentation import presentationHandle
from utils.print_string import *

# 程序主入口main()函数定义
def main():
    # 输出程序信息
    printImformation()
    # 输出启动信息
    printStarting()
    # 输出欢迎信息
    printWelcome()

    # 进入程序主循环，开始交互
    presentationHandle()
    
    # 输出退出信息
    printExit()

# 程序启动
if __name__ == "__main__": 
    main()