import torch
import torch.nn as nn
import torch.nn.functional as F

# 前馈神经网络
class FeedForward(nn.Module):
    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.d_ff = d_ff
        #两层线性变换
        self.linear1 = nn.Linear(d_model, d_ff)
        self.linear2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 第一层、激活函数
        x = F.relu(self.linear1(x))
        x = self.dropout(x)
        # 第二次
        x = self.linear2(x)

        return x
    
# 测试代码
def test_feed_forward():
    batch_size, seq_len, d_model = 2, 5, 4
    d_ff = 8
    x = torch.randn(batch_size, seq_len, d_model)
    ff = FeedForward(d_model, d_ff)
    output = ff(x)
    print(f"输入形状: {x.shape}")
    print(f"输出形状: {output.shape}")
    print(f"第一层权重形状: {ff.linear1.weight.shape}")
    print(f"第二层权重形状: {ff.linear2.weight.shape}")

if __name__ == "__main__":
    test_feed_forward()