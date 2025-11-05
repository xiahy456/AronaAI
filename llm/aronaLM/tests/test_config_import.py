import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from configs import MODEL_CONFIG, TRAINING_CONFIG

print(MODEL_CONFIG.d_ff)
print(TRAINING_CONFIG.batch_size)