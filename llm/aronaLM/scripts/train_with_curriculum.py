# scripts/train_with_curriculum.py
import torch
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def train_with_curriculum():
    """课程学习训练策略"""
    print("=== 课程学习训练 ===")
    
    from model.aronalm import AronaLM
    from data.dataloader import create_data_loader
    from model.tokenizer import tokenizer
    
    # 1. 创建模型
    model = AronaLM()
    print(f"模型参数量: {sum(p.numel() for p in model.parameters()):,}")
    
    # 2. 创建数据加载器
    train_loader = create_data_loader(
        "raw/training_dialogues.json",
        batch_size=8,
        shuffle=True
    )
    print(f"训练批次: {len(train_loader)}")
    
    # 3. 训练配置
    num_epochs = 300  # 更多epochs
    learning_rate = 0.0002  # 更低的学习率
    
    # 4. 优化器
    optimizer = torch.optim.AdamW(
        model.parameters(), 
        lr=learning_rate,
        weight_decay=0.02  # 更强的正则化
    )
    
    # 5. 学习率调度器（带warmup和衰减）
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=learning_rate * 2,  # 更高的max_lr
        epochs=num_epochs,
        steps_per_epoch=len(train_loader),
        pct_start=0.2,
        anneal_strategy='cos'
    )
    
    # 6. 训练循环
    model.train()
    best_loss = float('inf')
    patience = 20
    patience_counter = 0
    
    for epoch in range(num_epochs):
        total_loss = 0
        
        for batch in train_loader:
            input_ids = batch['input_ids']
            output_ids = batch['output_ids']
            
            # 前向传播
            optimizer.zero_grad()
            _, loss = model(input_ids, output_ids)
            
            # 反向传播
            loss.backward()
            
            # 梯度裁剪（更严格）
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.25)
            
            optimizer.step()
            scheduler.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(train_loader)
        
        # 定期评估
        if (epoch + 1) % 20 == 0 or epoch < 10:
            current_lr = optimizer.param_groups[0]['lr']
            print(f"Epoch [{epoch+1:3d}/{num_epochs}], Loss: {avg_loss:.4f}, LR: {current_lr:.6f}")
            
            # 评估生成质量
            model.eval()
            with torch.no_grad():
                test_cases = [
                    ("你好", "简单问候"),
                    ("今天天气怎么样", "日常对话")
                ]
                
                for test_input, desc in test_cases:
                    input_tokens = tokenizer.encode(test_input)
                    input_ids = torch.tensor([input_tokens], dtype=torch.long)
                    
                    generated = model.generate(
                        input_ids, 
                        max_length=25,
                        temperature=0.8
                    )
                    generated_text = tokenizer.decode(generated[0].tolist(), skip_special_tokens=True)
                    print(f"  {desc}: '{test_input}' → '{generated_text[:30]}...'")
            
            model.train()
        
        # 早停和保存最佳模型
        if avg_loss < best_loss:
            best_loss = avg_loss
            patience_counter = 0
            torch.save(model.state_dict(), "llm/aronaLM/checkpoints/best_curriculum_model.pt")
            print(f"  保存最佳模型，损失: {best_loss:.4f}")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"早停触发，epoch {epoch+1}")
                break
    
    print(f"\n训练完成！最佳损失: {best_loss:.4f}")
    
    # 最终测试
    print("\n=== 最终测试 ===")
    model.eval()
    model.load_state_dict(torch.load("llm/aronaLM/checkpoints/best_curriculum_model.pt"))
    
    final_test_cases = [
        "你好",
        "早上好阿罗娜",
        "今天需要处理文件"
    ]
    
    for test_input in final_test_cases:
        input_tokens = tokenizer.encode(test_input)
        input_ids = torch.tensor([input_tokens], dtype=torch.long)
        
        generated = model.generate(
            input_ids, 
            max_length=40,
            temperature=0.7
        )
        generated_text = tokenizer.decode(generated[0].tolist(), skip_special_tokens=True)
        print(f"老师: {test_input}")
        print(f"阿罗娜: {generated_text}")
        print()

if __name__ == "__main__":
    train_with_curriculum()