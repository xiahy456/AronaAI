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
from tqdm import tqdm
import sys
sys.path.append(str(Path(__file__).parent.parent))

from model.pretrain_model import PretrainLM
from data.dataloader import create_pretrain_dataloader
from configs import MODEL_CONFIG

class Pretrainer:
    """预训练训练器"""
    
    def __init__(self, config):
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"使用设备: {self.device}")
        
        # 创建模型
        self.model = PretrainLM().to(self.device)
        print(f"模型参数量: {sum(p.numel() for p in self.model.parameters()):,}")
        
        # 创建优化器
        self.optimizer = AdamW(
            self.model.parameters(),
            lr=config['learning_rate'],
            weight_decay=config['weight_decay']
        )
        
        # 创建保存目录
        self.checkpoint_dir = Path(config['checkpoint_dir'])
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.global_step = 0
        self.best_loss = float('inf')
        
    def train(self, train_loader, val_loader=None):
        """训练主循环"""
        
        # 创建学习率调度器
        total_steps = len(train_loader) * self.config['num_epochs']
        warmup_steps = self.config['warmup_steps']
        
        warmup_scheduler = LinearLR(
            self.optimizer,
            start_factor=0.01,
            end_factor=1.0,
            total_iters=warmup_steps
        )
        
        cosine_scheduler = CosineAnnealingLR(
            self.optimizer,
            T_max=total_steps - warmup_steps
        )
        
        scheduler = SequentialLR(
            self.optimizer,
            schedulers=[warmup_scheduler, cosine_scheduler],
            milestones=[warmup_steps]
        )
        
        print("开始预训练...")
        start_time = time.time()
        
        for epoch in range(self.config['num_epochs']):
            self.model.train()
            epoch_loss = 0
            
            progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{self.config['num_epochs']}")
            
            for batch_idx, batch in enumerate(progress_bar):
                # 数据移到设备
                input_ids = batch['input_ids'].to(self.device)
                labels = batch['labels'].to(self.device)
                
                # 前向传播
                logits, loss = self.model(input_ids, labels)
                
                # 反向传播
                loss = loss / self.config['gradient_accumulation_steps']
                loss.backward()
                
                # 梯度累积
                if (batch_idx + 1) % self.config['gradient_accumulation_steps'] == 0:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config['max_grad_norm'])
                    self.optimizer.step()
                    scheduler.step()
                    self.optimizer.zero_grad()
                    
                    self.global_step += 1
                    
                    # 记录损失
                    epoch_loss += loss.item() * self.config['gradient_accumulation_steps']
                    
                    # 更新进度条
                    progress_bar.set_postfix({
                        'loss': f"{loss.item() * self.config['gradient_accumulation_steps']:.4f}",
                        'lr': f"{scheduler.get_last_lr()[0]:.2e}"
                    })
                    
                    # 定期保存和评估
                    if self.global_step % self.config['save_steps'] == 0:
                        self.save_checkpoint(epoch, epoch_loss/(batch_idx+1))
                    
                    if self.global_step % self.config['eval_steps'] == 0 and val_loader:
                        val_loss = self.evaluate(val_loader)
                        print(f"\nStep {self.global_step}, Validation Loss: {val_loss:.4f}")
                        
                        if val_loss < self.best_loss:
                            self.best_loss = val_loss
                            self.save_checkpoint(epoch, val_loss, is_best=True)
                        
                        self.model.train()
            
            avg_epoch_loss = epoch_loss / len(train_loader)
            print(f"\nEpoch {epoch+1} 完成, 平均损失: {avg_epoch_loss:.4f}")
        
        total_time = time.time() - start_time
        print(f"预训练完成！总耗时: {total_time/3600:.2f} 小时")
        
        # 保存最终模型
        self.save_checkpoint(epoch, avg_epoch_loss, is_final=True)
    
    @torch.no_grad()
    def evaluate(self, val_loader):
        """评估"""
        self.model.eval()
        total_loss = 0
        
        for batch in tqdm(val_loader, desc="评估"):
            input_ids = batch['input_ids'].to(self.device)
            labels = batch['labels'].to(self.device)
            
            _, loss = self.model(input_ids, labels)
            total_loss += loss.item()
        
        return total_loss / len(val_loader)
    
    def save_checkpoint(self, epoch, loss, is_best=False, is_final=False):
        """保存检查点"""
        checkpoint = {
            'epoch': epoch,
            'global_step': self.global_step,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'loss': loss,
            'config': self.config
        }
        
        if is_best:
            path = self.checkpoint_dir / 'best_model.pt'
        elif is_final:
            path = self.checkpoint_dir / 'final_model.pt'
        else:
            path = self.checkpoint_dir / f'checkpoint_step_{self.global_step}.pt'
        
        torch.save(checkpoint, path)
        print(f"模型已保存: {path}")
    
    def load_checkpoint(self, path):
        """加载检查点"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.global_step = checkpoint['global_step']
        print(f"模型已加载: {path}")

# 运行预训练
def run_pretrain():
    """运行预训练"""
    import yaml
    
    # 加载配置
    with open('configs/pretrain_config.yaml', 'r') as f:
        config = yaml.safe_load(f)['pretrain']
    
    # 创建数据加载器
    train_loader = create_pretrain_dataloader(
        config['data_path'],
        batch_size=config['batch_size'],
        shuffle=True
    )
    
    val_loader = None
    if config.get('val_data_path'):
        val_loader = create_pretrain_dataloader(
            config['val_data_path'],
            batch_size=config['batch_size'],
            shuffle=False
        )
    
    # 创建训练器
    trainer = Pretrainer(config)
    
    # 开始训练
    trainer.train(train_loader, val_loader)

if __name__ == "__main__":
    run_pretrain()