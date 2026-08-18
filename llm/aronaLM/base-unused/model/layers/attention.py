import torch
import torch.nn as nn
import torch.nn.functional as F
import math

# 多头注意力机制
class MultiHeadAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        # 确保维度数被头数整除
        assert self.head_dim * n_heads == d_model, "d_model必须能被n_heads整除"
        # 线性变换层
        self.w_q = nn.Linear(d_model, d_model)  # 查询变换
        self.w_k = nn.Linear(d_model, d_model)  # 键变换
        self.w_v = nn.Linear(d_model, d_model)  # 值变换
        self.w_o = nn.Linear(d_model, d_model)  # 输出变换
        # dropout
        self.dropout = nn.Dropout(dropout)

    # 前向传播
    # Args:
    #   q: 查询张量 [batch_size, seq_len_q, d_model]
    #   k: 键张量 [batch_size, seq_len_k, d_model]
    #   v: 值张量 [batch_size, seq_len_v, d_model]
    #   mask: 注意力掩码
    def forward(self, q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, mask: torch.Tensor = None):
        batch_size, seq_len_q = q.size(0), q.size(1)
        seq_len_k = k.size(1)
        # 线性变换重塑为多头
        Q = self.w_q(q).view(batch_size, seq_len_q, self.n_heads, self.head_dim).transpose(1, 2)
        K = self.w_k(k).view(batch_size, seq_len_k, self.n_heads, self.head_dim).transpose(1, 2)
        V = self.w_v(v).view(batch_size, seq_len_k, self.n_heads, self.head_dim).transpose(1, 2)
        # 计算注意力分数
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.head_dim)
        # 应用掩码
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        # 计算注意力权重
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        # 应用注意力权重到值上
        attn_output = torch.matmul(attn_weights, V)
        # 合并多头
        attn_output = attn_output.transpose(1, 2).contiguous().view(
            batch_size, seq_len_q, self.d_model
        )
        # 输出变换
        output = self.w_o(attn_output)

        return output, attn_weights

# 测试多头注意力机制 
def test_multi_head_attention():
    batch_size, seq_len, d_model = 2, 5, 8
    n_heads = 4
    # 创建输入
    q = torch.randn(batch_size, seq_len, d_model)
    k = torch.randn(batch_size, seq_len, d_model)
    v = torch.randn(batch_size, seq_len, d_model)
    # 创建注意力模块
    attention = MultiHeadAttention(d_model, n_heads)
    # 前向传播
    output, attn_weights = attention(q, k, v)

    print(f"查询形状: {q.shape}")
    print(f"键形状: {k.shape}") 
    print(f"值形状: {v.shape}")
    print(f"输出形状: {output.shape}")
    print(f"注意力权重形状: {attn_weights.shape}")
    print(f"头数: {n_heads}")
    print(f"每个头维度: {attention.head_dim}")
    # 测试自注意力（q=k=v）
    print("\n--- 自注意力测试 ---")
    self_output, self_attn_weights = attention(q, q, q)
    print(f"自注意力输出形状: {self_output.shape}")
    print(f"自注意力权重形状: {self_attn_weights.shape}")
    # 检查注意力权重是否合理
    print(f"\n注意力权重和: {self_attn_weights.sum(dim=-1)[0, 0]}")  # 应该接近1

if __name__ == "__main__":
    test_multi_head_attention()