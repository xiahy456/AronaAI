import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from configs import MODEL_CONFIG
from model.transformer_block import TransformerBlock
from model.layers.position_encoding import PositionalEncoding

# 阿罗娜语言模型
class AronaLM(nn.Module):
    def __init__(self, config=MODEL_CONFIG):
        super().__init__()
        self.config = config
        #词嵌入层
        self.token_embedding = nn.Embedding(
            config.vocab_size,
            config.d_model,
            padding_idx=config.pad_token_id
        )
        # 位置编码
        self.pos_encoding = PositionalEncoding(
            config.d_model,
            config.max_seq_length
        )
        # Transformer层
        self.transformer_blocks = nn.ModuleList([
            TransformerBlock(
                config.d_model,
                config.n_heads,
                config.d_ff,
                config.dropout
            ) for _ in range(config.n_layers)
        ])
        # 输出层
        self.output_norm = nn.LayerNorm(config.d_model)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        # 权重绑定：输出层与嵌入层共享权重
        self.lm_head.weight = self.token_embedding.weight
        # 初始化权重
        self._init_weights()
        # 输出相关信息
        print(f"AronaLM模型初始化完成:")
        print(f"    词汇表大小: {config.vocab_size}")
        print(f"    模型维度: {config.d_model}")
        print(f"    Transformer层数: {config.n_layers}")
        print(f"    注意力头数: {config.n_heads}")
        print(f"    总参数量: {self._count_parameters():,}")

    # 初始化权重
    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    # 计算总参数量
    def _count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    # 前向传播
    # Args:
    #   input_ids: 输入token IDs [batch_size, seq_len]
    #   targets: 目标token IDs [batch_size, seq_len] 用于训练
    # Returns:
    #   logits: 预测logits [batch_size, seq_len, vacab_size]
    #   loss: 损失值（如果有targets）
    def forward(self, input_ids: torch.Tensor, targets: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        batch_size, seq_len = input_ids.shape
        # 词嵌入、位置编码
        x = self.token_embedding(input_ids)
        x = self.pos_encoding(x)
        # 通过Transformer层
        attention_weights = []
        for transformer_block in self.transformer_blocks: 
            x, attn_weights = transformer_block(x)
            attention_weights.append(attn_weights)
        # 输出层
        x = self.output_norm(x)
        logits = self.lm_head(x)
        # 计算损失
        loss = None
        if targets is not None:
            # 只计算非padding位置的损失
            loss_mask = (targets != self.config.pad_token_id).float()
            # 计算交叉熵损失
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=self.config.pad_token_id,
                reduction='mean'
            )

        return logits, loss
    
    # 生成回复
    # Args:
    #   input_ids: 起始token IDs [batch_size, seq_len]
    #   max_length: 生成的最大长度
    #   temperature: 生成温度
    # Returns:
    #   生成的token IDs [batch_size, generated_seq_len]
    def generate(self, input_ids: torch.Tensor, max_length:Optional[int] = None, temperature :Optional[float] = None) -> torch.Tensor:
        self.eval()

        max_length = max_length or self.config.max_gen_length
        temperature = temperature or self.config.temperature

        with torch.no_grad():
            for _ in range(max_length):
                # 前向传播
                logits, _ = self.forward(input_ids)
                # 获取最后一个token的logits
                next_token_logits = logits[:, -1, :] / temperature
                # 应用top-k采样
                if self.config.top_k > 0:
                    indices_to_remove = next_token_logits < torch.topk(next_token_logits, self.config.top_k)[0][..., -1, None]
                    next_token_logits[indices_to_remove] = -float('Inf')
                # 采样下一个token
                probs = F.softmax(next_token_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                # 检查是否生成了EOS token
                if next_token.item() == self.config.eos_token_id:
                    break
                # 将新token添加到序列中
                input_ids = torch.cat([input_ids, next_token], dim=1)
                # 如果序列太长，截断到最大长度
                if input_ids.size(1) > self.config.max_seq_length:
                    input_ids = input_ids[:, -self.config.max_seq_length:]
        return input_ids
    
# 测试阿罗娜语言模型
def test_aronalm():
    from model.tokenizer import tokenizer
    from configs import MODEL_CONFIG
    
    # 创建模型
    model = AronaLM()
    # 创建测试输入
    batch_size, seq_len = 2, 10
    vocab_size = MODEL_CONFIG.vocab_size
    # 随机生成输入
    input_ids = torch.randint(3, vocab_size, (batch_size, seq_len))

    # 测试
    print("====    模型前向传播测试    ====")
    logits, loss = model(input_ids)
    print(f"输入形状: {input_ids.shape}")
    print(f"输出logits形状: {logits.shape}")
    print(f"损失: {loss}（应为None）")
    print("\n====    模型训练测试    ====")
    targets = torch.randint(3, vocab_size, (batch_size, seq_len))
    logits, loss = model(input_ids, targets)
    print(f"目标形状: {targets.shape}")
    print(f"输出logits形状: {logits.shape}")
    print(f"损失值: {loss.item():.4f}")
    print(f"\n模型生成测试")
    start_text = "你好" # 测试输入文本
    start_tokens = tokenizer.encode(start_text)
    start_ids = torch.tensor([start_tokens], dtype=torch.long)
    print(f"起始文本: '{start_text}'")
    print(f"起始token: {start_tokens}")
    generated_ids = model.generate(start_ids, max_length=20)
    generated_tokens = generated_ids[0].tolist()
    generated_text = tokenizer.decode(generated_tokens)
    print(f"生成tokens: {generated_tokens}")
    print(f"生成文本: {generated_text}")
    print(f"\nAronaLM测试完成！")

if __name__ == "__main__":
    test_aronalm()