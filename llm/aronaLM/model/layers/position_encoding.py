import torch
import torch.nn as nn
import math

# 位置编码
class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_seq_len: int = 5000):
        super().__init__()
        self.d_model = d_model
        self.max_seq_len = max_seq_len
        # 预计算位置编码
        pe = torch.zeros(max_seq_len, d_model)
        position = torch.arange(0, max_seq_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        # 正弦编码
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        # 注册为buffer
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.size(1)
        return x + self.pe[:, :seq_len]

# 测试代码
def test_positional_encoding():
    batch_size, seq_len, d_model = 2, 10, 8
    x = torch.randn(batch_size, seq_len, d_model)
    pos_encoding = PositionalEncoding(d_model)
    output = pos_encoding(x)
    print(f"输入形状: {x.shape}")
    print(f"输出形状: {output.shape}")
    print(f"位置编码形状: {pos_encoding.pe.shape}")
    print(f"编码位置示例(前5个位置、前4个维度): ")
    print(pos_encoding.pe[0, :5, :4])

if __name__ == "__main__":
    test_positional_encoding()