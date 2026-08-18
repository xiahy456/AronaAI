# model/pretrain_model.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from configs import MODEL_CONFIG

class PretrainLM(nn.Module):
    """预训练语言模型"""
    
    def __init__(self, config=MODEL_CONFIG):
        super().__init__()
        self.config = config
        
        # 词嵌入
        self.token_embedding = nn.Embedding(
            config.vocab_size,
            config.d_model,
            padding_idx=config.pad_token_id
        )
        
        # 位置编码
        self.pos_encoding = self._create_positional_encoding()
        
        # Transformer层
        self.layers = nn.ModuleList([
            TransformerLayer(config) for _ in range(config.n_layers)
        ])
        
        # 输出层
        self.ln_f = nn.LayerNorm(config.d_model)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        
        # 权重绑定
        self.lm_head.weight = self.token_embedding.weight
        
        self._init_weights()
        
    def _create_positional_encoding(self):
        """创建正弦位置编码"""
        pe = torch.zeros(self.config.max_seq_length, self.config.d_model)
        position = torch.arange(0, self.config.max_seq_length, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, self.config.d_model, 2).float() * 
                           (-math.log(10000.0) / self.config.d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # [1, seq_len, d_model]
        
        return nn.Parameter(pe, requires_grad=False)
    
    def _init_weights(self):
        """初始化权重"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
    
    def forward(self, input_ids, labels=None):
        """
        Args:
            input_ids: [batch_size, seq_len]
            labels: [batch_size, seq_len]
        """
        batch_size, seq_len = input_ids.shape
        
        # 词嵌入 + 位置编码
        x = self.token_embedding(input_ids)  # [batch_size, seq_len, d_model]
        x = x + self.pos_encoding[:, :seq_len, :]
        
        # 通过Transformer层
        for layer in self.layers:
            x = layer(x)
        
        # 输出层
        x = self.ln_f(x)
        logits = self.lm_head(x)  # [batch_size, seq_len, vocab_size]
        
        loss = None
        if labels is not None:
            # 计算损失（忽略padding部分）
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                labels.view(-1),
                ignore_index=self.config.pad_token_id
            )
        
        return logits, loss
    
    @torch.no_grad()
    def generate(self, input_ids, max_new_tokens=50, temperature=0.8, top_k=50):
        """生成文本"""
        self.eval()
        
        for _ in range(max_new_tokens):
            # 获取当前序列
            if input_ids.size(1) > self.config.max_seq_length:
                current_ids = input_ids[:, -self.config.max_seq_length:]
            else:
                current_ids = input_ids
            
            # 前向传播
            logits, _ = self.forward(current_ids)
            next_token_logits = logits[:, -1, :] / temperature
            
            # top-k采样
            if top_k > 0:
                values, _ = torch.topk(next_token_logits, top_k)
                min_values = values[:, -1].unsqueeze(-1)
                next_token_logits = torch.where(
                    next_token_logits < min_values,
                    torch.tensor(-float('inf')).to(next_token_logits.device),
                    next_token_logits
                )
            
            # 采样
            probs = F.softmax(next_token_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            
            # 添加到序列
            input_ids = torch.cat([input_ids, next_token], dim=1)
            
            # 检查EOS
            if next_token.item() == self.config.eos_token_id:
                break
        
        return input_ids

class TransformerLayer(nn.Module):
    """单层Transformer"""
    
    def __init__(self, config):
        super().__init__()
        self.attn = MultiHeadAttention(config)
        self.ffn = FeedForward(config)
        self.ln1 = nn.LayerNorm(config.d_model)
        self.ln2 = nn.LayerNorm(config.d_model)
        
    def forward(self, x):
        # 自注意力 + 残差连接
        attn_out = self.attn(x)
        x = self.ln1(x + attn_out)
        
        # 前馈网络 + 残差连接
        ffn_out = self.ffn(x)
        x = self.ln2(x + ffn_out)
        
        return x

class MultiHeadAttention(nn.Module):
    """多头注意力"""
    
    def __init__(self, config):
        super().__init__()
        self.num_heads = config.n_heads
        self.head_dim = config.d_model // config.n_heads
        
        self.qkv = nn.Linear(config.d_model, 3 * config.d_model)
        self.proj = nn.Linear(config.d_model, config.d_model)
        
    def forward(self, x):
        batch_size, seq_len, d_model = x.shape
        
        # 计算Q, K, V
        qkv = self.qkv(x).reshape(batch_size, seq_len, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # [3, batch, heads, seq_len, head_dim]
        q, k, v = qkv[0], qkv[1], qkv[2]
        
        # 注意力分数
        scale = 1.0 / math.sqrt(self.head_dim)
        attn = torch.matmul(q, k.transpose(-2, -1)) * scale
        
        # 因果掩码（只关注左侧）
        causal_mask = torch.triu(torch.ones(seq_len, seq_len, device=x.device) * float('-inf'), diagonal=1)
        attn = attn + causal_mask.unsqueeze(0).unsqueeze(0)
        
        attn = F.softmax(attn, dim=-1)
        
        # 应用注意力
        out = torch.matmul(attn, v)
        out = out.transpose(1, 2).reshape(batch_size, seq_len, d_model)
        out = self.proj(out)
        
        return out

class FeedForward(nn.Module):
    """前馈网络"""
    
    def __init__(self, config):
        super().__init__()
        self.fc1 = nn.Linear(config.d_model, config.d_ff)
        self.fc2 = nn.Linear(config.d_ff, config.d_model)
        self.act = nn.GELU()
        
    def forward(self, x):
        return self.fc2(self.act(self.fc1(x)))