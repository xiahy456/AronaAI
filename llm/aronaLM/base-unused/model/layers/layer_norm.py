import torch
import torch.nn as nn

# 层归一化
class LayerNorm(nn.Module):
    def __init__(self, d_model: int, eps: float = 1e-5):
        super().__init__()
        self.d_model = d_model
        self.eps = eps
        # 可学习参数
        self.gamma = nn.Parameter(torch.ones(d_model))  # 缩放参数
        self.beta = nn.Parameter(torch.zeros(d_model))  # 偏置参数

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 计算均值和方差
        mean = x.mean(dim=-1, keepdim=True)
        var = x.var(dim=-1,keepdim=True, unbiased=False)
        # 归一化
        x_normalized = (x-mean) / torch.sqrt(var + self.eps)
        # 缩放和偏移
        return self.gamma * x_normalized + self.beta
    
# 测试代码
def test_layer_norm():
    # 测试层归一化
    batch_size, seq_len, d_model = 2, 5, 4
    x = torch.randn(batch_size, seq_len, d_model)
    layer_norm = LayerNorm(d_model)
    output = layer_norm(x)

    print(f"输入形状: {x.shape}")
    print(f"输出形状: {output.shape}")
    print(f"gamma形状: {layer_norm.gamma.shape}")
    print(f"beta形状: {layer_norm.beta.shape}")
    # 检查归一化效果
    output_mean = output.mean(dim=-1)
    output_std = output.std(dim=-1)
    print(f"输出均值: {output_mean}")
    print(f"输出标准差: {output_std}")

if __name__ == "__main__":
    test_layer_norm()

