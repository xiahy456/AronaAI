import torch
import sys
import os
from pathlib import Path
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 抑制不必要的输出
import warnings
warnings.filterwarnings('ignore')

def train_quick():
    # 快速训练模型（改进版）
    print("=== 快速训练模型 ===")
    
    # 只在开始时初始化一次分词器
    from model.tokenizer import tokenizer
    print(f"词汇表大小: {tokenizer.get_vocab_size()}")
    
    from model.aronalm import AronaLM
    from data.dataloader import create_data_loader
    
    # 创建检查点checkpoints目录
    checkpoint_dir = Path("llm/aronaLM/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    print(f"检查点目录: {checkpoint_dir.absolute()}")

    # 1. 创建模型
    print("1. 创建模型...")
    model = AronaLM()
    
    # 2. 创建数据加载器
    print("2. 创建数据加载器...")
    train_loader = create_data_loader(
        "raw/training_dialogues.json",
        batch_size=4,
        shuffle=True
    )
    print(f"训练批次: {len(train_loader)}")
    
    # 3. 训练配置
    num_epochs = 100  # 100次
    learning_rate = 0.001
    
    # 4. 优化器
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    
    # 5. 学习率调度器
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
    
    # 6. 训练循环
    print("3. 开始训练...")
    model.train()
    
    best_loss = float('inf')
    
    for epoch in range(num_epochs):
        total_loss = 0
        for batch_idx, batch in enumerate(train_loader):
            input_ids = batch['input_ids']
            output_ids = batch['output_ids']
            
            # 前向传播
            optimizer.zero_grad()
            _, loss = model(input_ids, output_ids)
            
            # 反向传播
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(train_loader)
        scheduler.step()
        
        # 每20个epoch输出一次
        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1:3d}/{num_epochs}], Loss: {avg_loss:.4f}, LR: {scheduler.get_last_lr()[0]:.6f}")
            
            # 测试生成
            model.eval()
            with torch.no_grad():
                test_input = "你好"
                input_tokens = tokenizer.encode(test_input)
                input_ids = torch.tensor([input_tokens], dtype=torch.long)
                
                generated = model.generate(input_ids, max_length=20, temperature=0.8)
                generated_text = tokenizer.decode(generated[0].tolist())
                
                # 清理生成文本
                generated_text = generated_text.replace("[EOS]", "").strip()
                print(f"  测试输入: '{test_input}'")
                print(f"  生成结果: '{generated_text}'")
            
            model.train()
        
        # 保存最佳模型
        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save(model.state_dict(), "llm/aronaLM/checkpoints/best_model.pt")
    
    print("4. 保存最终模型...")
    torch.save(model.state_dict(), "llm/aronaLM/checkpoints/final_model.pt")
    print(f"✅ 训练完成！最佳损失: {best_loss:.4f}")

if __name__ == "__main__":
    train_quick()