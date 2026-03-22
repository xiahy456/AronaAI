# scripts/test_checkpoint.py
import torch
import sys
import os
from pathlib import Path
# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.append('.')
from model.pretrain_model import PretrainLM
from model.tokenizer import tokenizer
from configs import MODEL_CONFIG

def test_checkpoint(checkpoint_path, test_prompts=None):
    """测试检查点模型"""
    
    if test_prompts is None:
        test_prompts = [
            "你好",
            "今天天气",
            "我喜欢",
            "人工智能",
            "机器学习"
        ]
    
    print("="*60)
    print(f"测试检查点: {checkpoint_path}")
    print("="*60)
    
    # 加载模型
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"使用设备: {device}")
    
    model = PretrainLM().to(device)
    
    # 加载检查点
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # 打印检查点信息
    print(f"\n检查点信息:")
    print(f"  - 步数: {checkpoint['global_step']:,}")
    print(f"  - Epoch: {checkpoint['epoch']+1}")
    print(f"  - 损失: {checkpoint['loss']:.4f}")
    
    # 测试生成
    print(f"\n{'='*60}")
    print("生成测试:")
    print("="*60)
    
    for prompt in test_prompts:
        print(f"\n输入: {prompt}")
        
        # 编码
        input_ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long).to(device)
        
        # 生成
        with torch.no_grad():
            output_ids = model.generate(
                input_ids,
                max_new_tokens=30,
                temperature=0.8,
                top_k=40
            )
        
        # 解码
        generated = tokenizer.decode(output_ids[0].tolist(), skip_special_tokens=True)
        
        # 只显示生成的部分（去掉输入）
        if generated.startswith(prompt):
            generated = generated[len(prompt):]
        
        print(f"输出: {generated}")
    
    print("\n" + "="*60)
    
    return model

def get_latest_checkpoint(checkpoint_dir):
    """获取最新的检查点"""
    checkpoint_dir = Path(checkpoint_dir)
    checkpoints = list(checkpoint_dir.glob("checkpoint_step_*.pt"))
    
    if not checkpoints:
        return None
    
    # 按修改时间排序，取最新的
    checkpoints.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return checkpoints[0]

def monitor_training_continuously(checkpoint_dir, interval=300):
    """持续监控训练进度（每5分钟测试一次）"""
    import time
    
    print("开始持续监控训练...")
    last_step = 0
    
    while True:
        # 获取最新检查点
        latest = get_latest_checkpoint(checkpoint_dir)
        
        if latest:
            checkpoint = torch.load(latest, map_location='cpu')
            current_step = checkpoint['global_step']
            
            if current_step > last_step:
                print(f"\n{'='*60}")
                print(f"新检查点发现 - 步数: {current_step:,}")
                print(f"{'='*60}")
                
                # 测试最新模型
                test_checkpoint(latest)
                last_step = current_step
        
        # 等待下次检查
        time.sleep(interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试预训练检查点")
    parser.add_argument('--checkpoint', type=str, default=None, 
                       help="检查点路径（不指定则使用最新的）")
    parser.add_argument('--monitor', action='store_true',
                       help="持续监控模式，每5分钟测试最新检查点")
    args = parser.parse_args()
    
    checkpoint_dir = "/root/autodl-tmp/checkpoint/pretrain_large"
    
    if args.monitor:
        # 持续监控模式
        monitor_training_continuously(checkpoint_dir)
    else:
        # 单次测试模式
        if args.checkpoint:
            checkpoint_path = args.checkpoint
        else:
            checkpoint_path = get_latest_checkpoint(checkpoint_dir)
            
        if checkpoint_path:
            test_checkpoint(checkpoint_path)
        else:
            print("未找到检查点文件")