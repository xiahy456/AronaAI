import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from training.trainer import main

if __name__ == "__main__":
    main()