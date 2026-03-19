# training/pretrainer.py
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR
import os
from pathlib import Path
import json
import time
import yaml
from tqdm import tqdm
import sys
import psutil
import gc
import argparse
from datetime import datetime
sys.path.append(str(Path(__file__).parent.parent))

from model.pretrain_model import PretrainLM
from configs import MODEL_CONFIG

# 预训练数据集类
class PretrainDataset(torch.utils.data.Dataset):
    """预训练数据集"""
    
    def __init__(self, data_path, max_seq_length=128):
        self.data_path = data_path
        self.max_seq_length = max_seq_length
        self.samples = self._load_samples()
        print(f"加载了 {len(self.samples)} 个预训练样本")
        
    def _load_samples(self):
        """加载样本"""
        samples = []
        with open(self.data_path, 'r', encoding='utf-8') as f:
            for line in f:
                sample = json.loads(line)
                samples.append(sample['token_ids'])
        return samples
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        token_ids = self.samples[idx].copy()
        
        # 添加EOS token
        token_ids.append(1)  # eos_token_id
        
        # 截断或填充
        if len(token_ids) > self.max_seq_length:
            token_ids = token_ids[:self.max_seq_length]
        else:
            padding = [0] * (self.max_seq_length - len(token_ids))  # pad_token_id
            token_ids = token_ids + padding
        
        # 对于因果语言建模，输入和目标是一样的（偏移一位）
        input_ids = torch.tensor(token_ids[:-1], dtype=torch.long)
        labels = torch.tensor(token_ids[1:], dtype=torch.long)
        
        return {
            'input_ids': input_ids,
            'labels': labels
        }

def create_pretrain_dataloader(data_path, batch_size=24, shuffle=True, num_workers=4, max_seq_length=128):
    """创建预训练数据加载器"""
    dataset = PretrainDataset(data_path, max_seq_length)
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
        prefetch_factor=2,
        persistent_workers=True if num_workers > 0 else False,
        drop_last=True
    )
    return dataloader

class Pretrainer:
    """预训练训练器 - 支持RTX 4090优化"""
    
    def __init__(self, config):
        """
        初始化训练器
        
        Args:
            config: 训练配置字典
        """
        self.config = config
        
        # 设置设备
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"使用设备: {self.device}")
        
        if torch.cuda.is_available():
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        
        # 创建模型
        self.model = PretrainLM().to(self.device)
        self.print_model_info()
        
        # 创建优化器
        self.optimizer = self._create_optimizer()
        
        # 混合精度训练
        self.use_amp = True
        if self.use_amp and torch.cuda.is_available():
            self.scaler = torch.cuda.amp.GradScaler()
            print("使用混合精度训练(AMP)")
        
        # 创建保存目录
        self.checkpoint_dir = Path(config['checkpoint_dir'])
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        print(f"检查点保存路径: {self.checkpoint_dir.absolute()}")
        
        # 训练状态
        self.global_step = 0
        self.current_epoch = 0
        self.best_loss = float('inf')
        self.train_losses = []
        self.val_losses = []
        
        # 内存监控
        self.memory_limit_gb = 20  # 4090有24GB，留点余量
        self.last_gc_time = time.time()
        
        # 日志文件
        self.log_file = None
        if 'log_file' in config:
            self.log_file = open(config['log_file'], 'w', encoding='utf-8')
    
    def log(self, message):
        """记录日志到文件和终端"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        if self.log_file:
            self.log_file.write(log_msg + '\n')
            self.log_file.flush()
    
    def print_model_info(self):
        """打印模型信息"""
        total_params = sum(p.numel() for p in self.model.parameters())
        trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        
        self.log(f"模型参数量: {total_params:,}")
        self.log(f"可训练参数量: {trainable_params:,}")
        self.log(f"模型配置: d_model={MODEL_CONFIG.d_model}, "
              f"n_layers={MODEL_CONFIG.n_layers}, "
              f"n_heads={MODEL_CONFIG.n_heads}")
    
    def _create_optimizer(self):
        """创建优化器"""
        no_decay = ['bias', 'LayerNorm.weight']
        optimizer_grouped_parameters = [
            {
                'params': [p for n, p in self.model.named_parameters() 
                          if not any(nd in n for nd in no_decay)],
                'weight_decay': self.config['weight_decay'],
            },
            {
                'params': [p for n, p in self.model.named_parameters() 
                          if any(nd in n for nd in no_decay)],
                'weight_decay': 0.0,
            }
        ]
        
        return AdamW(
            optimizer_grouped_parameters,
            lr=self.config['learning_rate'],
            betas=(0.9, 0.999),
            eps=1e-8
        )
    
    def _create_scheduler(self, train_loader):
        """创建学习率调度器"""
        total_steps = len(train_loader) * self.config['num_epochs']
        warmup_steps = self.config.get('warmup_steps', 2000)
        
        # Warmup阶段
        warmup_scheduler = LinearLR(
            self.optimizer,
            start_factor=0.01,
            end_factor=1.0,
            total_iters=warmup_steps
        )
        
        # Cosine退火阶段
        cosine_scheduler = CosineAnnealingLR(
            self.optimizer,
            T_max=max(1, total_steps - warmup_steps),
            eta_min=self.config['learning_rate'] * 0.01
        )
        
        # 组合调度器
        scheduler = SequentialLR(
            self.optimizer,
            schedulers=[warmup_scheduler, cosine_scheduler],
            milestones=[warmup_steps]
        )
        
        return scheduler
    
    def check_memory(self):
        """检查内存使用情况"""
        if self.device.type == 'cuda':
            allocated = torch.cuda.memory_allocated() / 1024**3
            cached = torch.cuda.memory_reserved() / 1024**3
            if allocated > self.memory_limit_gb:
                self.log(f"⚠️ GPU内存使用过高: {allocated:.1f} GB / {cached:.1f} GB")
                torch.cuda.empty_cache()
                return True
        
        # 系统内存检查
        memory_usage = psutil.Process().memory_info().rss / 1024**3
        if memory_usage > 80:  # 系统内存限制
            if time.time() - self.last_gc_time > 300:
                gc.collect()
                self.last_gc_time = time.time()
                self.log(f"⚠️ 系统内存使用: {memory_usage:.1f} GB，执行GC")
            return True
        
        return False
    
    def train_epoch(self, train_loader, epoch, scheduler):
        """训练一个epoch"""
        self.model.train()
        total_loss = 0
        num_batches = len(train_loader)
        
        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{self.config['num_epochs']}")
        
        for batch_idx, batch in enumerate(progress_bar):
            # 数据移到设备
            input_ids = batch['input_ids'].to(self.device)
            labels = batch['labels'].to(self.device)
            
            if self.use_amp and torch.cuda.is_available():
                # 混合精度前向传播
                with torch.cuda.amp.autocast():
                    logits, loss = self.model(input_ids, labels)
                    loss = loss / self.config['gradient_accumulation_steps']
                
                # 反向传播
                self.scaler.scale(loss).backward()
                
                # 梯度累积步进
                if (batch_idx + 1) % self.config['gradient_accumulation_steps'] == 0:
                    # 梯度裁剪
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(), 
                        self.config['max_grad_norm']
                    )
                    
                    # 优化器步进
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                    scheduler.step()
                    self.optimizer.zero_grad()
                    
                    self.global_step += 1
                    
                    # 记录损失
                    current_loss = loss.item() * self.config['gradient_accumulation_steps']
                    total_loss += current_loss
                    
                    # 更新进度条
                    progress_bar.set_postfix({
                        'loss': f"{current_loss:.4f}",
                        'lr': f"{scheduler.get_last_lr()[0]:.2e}",
                        'step': self.global_step
                    })
                    
                    # 定期保存和评估
                    if self.global_step % self.config['save_steps'] == 0:
                        self.save_checkpoint(epoch, total_loss/(batch_idx+1))
                    
                    if self.global_step % self.config['eval_steps'] == 0:
                        val_loss = self.evaluate(train_loader)
                        self.log(f"\nStep {self.global_step}, Quick Eval Loss: {val_loss:.4f}")
                    
                    # 检查内存
                    self.check_memory()
            else:
                # 普通精度训练
                logits, loss = self.model(input_ids, labels)
                loss = loss / self.config['gradient_accumulation_steps']
                loss.backward()
                
                if (batch_idx + 1) % self.config['gradient_accumulation_steps'] == 0:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(), 
                        self.config['max_grad_norm']
                    )
                    self.optimizer.step()
                    scheduler.step()
                    self.optimizer.zero_grad()
                    
                    self.global_step += 1
                    current_loss = loss.item() * self.config['gradient_accumulation_steps']
                    total_loss += current_loss
                    
                    progress_bar.set_postfix({
                        'loss': f"{current_loss:.4f}",
                        'lr': f"{scheduler.get_last_lr()[0]:.2e}",
                        'step': self.global_step
                    })
                    
                    if self.global_step % self.config['save_steps'] == 0:
                        self.save_checkpoint(epoch, total_loss/(batch_idx+1))
                    
                    if self.global_step % self.config['eval_steps'] == 0:
                        val_loss = self.evaluate(train_loader)
                        self.log(f"\nStep {self.global_step}, Quick Eval Loss: {val_loss:.4f}")
            
            # 定期记录日志
            if self.global_step % self.config['logging_steps'] == 0 and self.global_step > 0:
                avg_loss = total_loss / ((batch_idx + 1) // self.config['gradient_accumulation_steps'])
                self.train_losses.append((self.global_step, avg_loss))
        
        avg_epoch_loss = total_loss / (num_batches // self.config['gradient_accumulation_steps'])
        return avg_epoch_loss
    
    @torch.no_grad()
    def evaluate(self, val_loader):
        """评估模型"""
        self.model.eval()
        total_loss = 0
        num_batches = 0
        
        for batch in val_loader:
            input_ids = batch['input_ids'].to(self.device)
            labels = batch['labels'].to(self.device)
            
            _, loss = self.model(input_ids, labels)
            total_loss += loss.item()
            num_batches += 1
            
            if num_batches >= 100:
                break
        
        avg_loss = total_loss / num_batches
        self.val_losses.append((self.global_step, avg_loss))
        
        return avg_loss
    
    def save_checkpoint(self, epoch, loss, is_best=False, is_final=False):
        """保存检查点"""
        checkpoint = {
            'epoch': epoch,
            'global_step': self.global_step,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'loss': loss,
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'config': self.config
        }
        
        if self.use_amp and hasattr(self, 'scaler'):
            checkpoint['scaler_state_dict'] = self.scaler.state_dict()
        
        if is_best:
            path = self.checkpoint_dir / 'best_model.pt'
        elif is_final:
            path = self.checkpoint_dir / 'final_model.pt'
        else:
            path = self.checkpoint_dir / f'checkpoint_step_{self.global_step}.pt'
        
        torch.save(checkpoint, path)
        
        file_size = path.stat().st_size / 1024 / 1024
        self.log(f"💾 模型已保存: {path} ({file_size:.1f} MB)")
        
        # 删除旧的检查点，只保留最近3个
        self._cleanup_old_checkpoints()
    
    def _cleanup_old_checkpoints(self):
        """清理旧的检查点，只保留最近3个"""
        checkpoints = sorted(self.checkpoint_dir.glob('checkpoint_step_*.pt'))
        if len(checkpoints) > 3:
            for old_cp in checkpoints[:-3]:
                old_cp.unlink()
                self.log(f"🗑️ 删除旧检查点: {old_cp.name}")
    
    def load_checkpoint(self, checkpoint_path):
        """加载检查点"""
        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            self.log(f"错误: 检查点不存在 {checkpoint_path}")
            return None
        
        self.log(f"加载检查点: {checkpoint_path}")
        
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.global_step = checkpoint['global_step']
        self.current_epoch = checkpoint['epoch']
        self.train_losses = checkpoint.get('train_losses', [])
        self.val_losses = checkpoint.get('val_losses', [])
        
        if self.use_amp and 'scaler_state_dict' in checkpoint:
            self.scaler.load_state_dict(checkpoint['scaler_state_dict'])
        
        self.log(f"恢复训练: epoch={self.current_epoch}, step={self.global_step}")
        
        return checkpoint
    
    def train(self, train_loader, val_loader=None, resume_from=None):
        """
        完整训练流程
        """
        # 恢复训练
        if resume_from:
            self.load_checkpoint(resume_from)
        
        # 创建学习率调度器
        scheduler = self._create_scheduler(train_loader)
        
        self.log("开始训练...")
        start_time = time.time()
        
        for epoch in range(self.current_epoch, self.config['num_epochs']):
            epoch_start = time.time()
            
            # 训练一个epoch
            train_loss = self.train_epoch(train_loader, epoch, scheduler)
            
            # 验证
            val_loss = None
            if val_loader:
                val_loss = self.evaluate(val_loader)
            
            # 打印epoch结果
            epoch_time = time.time() - epoch_start
            self.log(f"\nEpoch {epoch+1}/{self.config['num_epochs']} 完成:")
            self.log(f"  训练损失: {train_loss:.4f}")
            if val_loss is not None:
                self.log(f"  验证损失: {val_loss:.4f}")
            self.log(f"  学习率: {scheduler.get_last_lr()[0]:.6f}")
            self.log(f"  耗时: {epoch_time:.2f}秒")
            self.log("-" * 60)
            
            # 保存epoch检查点
            self.save_checkpoint(epoch, train_loss)
            
            # 保存最佳模型
            if val_loss and val_loss < self.best_loss:
                self.best_loss = val_loss
                self.save_checkpoint(epoch, val_loss, is_best=True)
            
            self.current_epoch = epoch + 1
        
        total_time = time.time() - start_time
        self.log(f"\n训练完成！总耗时: {total_time/3600:.2f} 小时")
        self.log(f"最佳损失: {self.best_loss:.4f}")
        
        # 保存最终模型
        self.save_checkpoint(epoch, train_loss, is_final=True)
        
        if self.log_file:
            self.log_file.close()
    
    def generate_sample(self, prompt, max_length=50, temperature=0.8):
        """生成示例文本"""
        from model.tokenizer import tokenizer
        
        self.model.eval()
        
        # 编码输入
        input_ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long).to(self.device)
        
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids,
                max_new_tokens=max_length,
                temperature=temperature
            )
        
        # 解码
        generated = tokenizer.decode(output_ids[0].tolist(), skip_special_tokens=True)
        
        return generated

def load_config(config_path):
    """加载配置，支持绝对路径"""
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    print(f"加载配置文件: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)['pretrain']
    
    # 确保数值类型正确
    numeric_fields = [
        'max_seq_length', 'batch_size', 'learning_rate', 'weight_decay',
        'num_epochs', 'warmup_steps', 'save_steps', 'eval_steps',
        'gradient_accumulation_steps', 'max_grad_norm', 'logging_steps'
    ]
    
    for field in numeric_fields:
        if field in config and config[field] is not None:
            if field in ['learning_rate', 'weight_decay', 'max_grad_norm']:
                config[field] = float(config[field])
            else:
                config[field] = int(config[field])
    
    # 路径处理
    for key in ['data_path', 'val_data_path', 'checkpoint_dir']:
        if key in config and config[key]:
            path = Path(config[key])
            if not path.is_absolute():
                config[key] = str(Path.cwd() / config[key])
            else:
                config[key] = str(path)
    
    return config

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="预训练脚本")
    parser.add_argument('--config', type=str, required=True, help="配置文件路径")
    parser.add_argument('--resume', type=str, default=None, help="恢复训练的检查点路径")
    parser.add_argument('--log_file', type=str, default=None, help="日志文件路径")
    parser.add_argument('--debug', action='store_true', help="调试模式")
    args = parser.parse_args()
    
    print("="*60)
    print("预训练开始")
    print("="*60)
    
    try:
        # 加载配置
        config = load_config(args.config)
        
        # 添加日志文件
        if args.log_file:
            config['log_file'] = args.log_file
        
        # 调试模式
        if args.debug:
            config['num_epochs'] = 1
            config['batch_size'] = 4
            config['gradient_accumulation_steps'] = 1
            config['save_steps'] = 10
            config['eval_steps'] = 5
            print("调试模式已开启")
        
        # 打印配置
        print(f"\n=== 训练配置 ===")
        print(f"数据路径: {config['data_path']}")
        print(f"验证路径: {config['val_data_path']}")
        print(f"检查点路径: {config['checkpoint_dir']}")
        print(f"批次大小: {config['batch_size']}")
        print(f"梯度累积步数: {config['gradient_accumulation_steps']}")
        print(f"有效批次大小: {config['batch_size'] * config['gradient_accumulation_steps']}")
        print(f"学习率: {config['learning_rate']}")
        print(f"训练轮数: {config['num_epochs']}")
        print()
        
        # 检查数据文件
        data_path = Path(config['data_path'])
        if not data_path.exists():
            print(f"错误: 数据文件不存在 {data_path}")
            return
        
        file_size = data_path.stat().st_size / 1024**3
        print(f"数据文件大小: {file_size:.2f} GB")
        
        # 检查验证文件
        val_path = None
        if config.get('val_data_path'):
            val_path = Path(config['val_data_path'])
            if val_path.exists():
                val_size = val_path.stat().st_size / 1024**3
                print(f"验证文件大小: {val_size:.2f} GB")
            else:
                print(f"警告: 验证文件不存在 {val_path}，将不使用验证集")
                val_path = None
        
        # 创建数据加载器
        print("\n创建数据加载器...")
        train_loader = create_pretrain_dataloader(
            str(data_path),
            batch_size=config['batch_size'],
            shuffle=True,
            num_workers=0 if args.debug else 4,
            max_seq_length=config['max_seq_length']
        )
        
        val_loader = None
        if val_path and val_path.exists():
            val_loader = create_pretrain_dataloader(
                str(val_path),
                batch_size=config['batch_size'],
                shuffle=False,
                num_workers=0 if args.debug else 2,
                max_seq_length=config['max_seq_length']
            )
            print(f"验证数据加载器创建完成，批次: {len(val_loader)}")
        
        print(f"训练数据加载器创建完成，批次: {len(train_loader)}")
        
        # 检查恢复路径
        resume_path = None
        if args.resume:
            resume_path = Path(args.resume)
            if not resume_path.exists():
                print(f"警告: 恢复路径不存在 {resume_path}，将从头开始训练")
                resume_path = None
        
        # 创建训练器
        trainer = Pretrainer(config)
        
        # 开始训练
        trainer.train(train_loader, val_loader, resume_from=resume_path)
        
        # 测试生成
        print("\n生成示例:")
        sample_text = trainer.generate_sample("你好", max_length=30)
        print(f"输入: 你好")
        print(f"输出: {sample_text}")
        
    except Exception as e:
        print(f"\n❌ 训练过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()