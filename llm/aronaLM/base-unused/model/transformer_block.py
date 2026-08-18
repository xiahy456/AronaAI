import torch
import torch.nn as nn
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model.layers.attention import MultiHeadAttention
from model.layers.feed_forward import FeedForward
from model.layers.layer_norm import LayerNorm

# Transformer块：多头注意力+前馈网络
class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_ff = d_ff
        # 自注意力层
        self.self_attention = MultiHeadAttention(d_model, n_heads, dropout)
        self.norm1 = LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        # 前馈网络层
        self.feed_forward = FeedForward(d_model, d_ff, dropout)
        self.norm2 = LayerNorm(d_model)
        self.dropout2 = nn.Dropout(dropout)

    # 前向传播
    # Args:
    #   x: 输入张量 [batch_size, seq_len, d_model]
    #   mask: 注意力掩码
    def forward(self, x: torch.Tensor, mask: torch.Tensor = None):
        #自注意力子层（带残差连接和层归一化）
        attn_output, attn_weights = self.self_attention(x, x, x, mask)
        x = x + self.dropout1(attn_output)
        x = self.norm1(x)
        # 前馈网络子层（带残差连接和层归一化）
        ff_output = self.feed_forward(x)
        x = x + self.dropout2(ff_output)
        x = self.norm2(x)

        return x, attn_weights
    
# 测试Transformer块
def test_transformer_block():
    batch_size, seq_len, d_model = 2, 5, 8
    n_heads = 4
    d_ff = 16
    # 创建输入
    x = torch.randn(batch_size, seq_len, d_model)
    # 创建Transformer块
    transformer_block = TransformerBlock(d_model, n_heads, d_ff)
    # 前向传播
    output, attn_weights = transformer_block(x)

    print(f"输入形状: {x.shape}")
    print(f"输出形状: {output.shape}")
    print(f"注意力权重形状: {attn_weights.shape}")
    # 检查输入输出形状是否一致
    assert x.shape == output.shape, "输入输出形状应该一致"
    print("Transformer块测试通过！")

if __name__ == "__main__":
    test_transformer_block()