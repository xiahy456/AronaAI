import torch
import matplotlib.pyplot as plt
from pathlib import Path

# 绘制训练历史
def plot_training_history(trainer, save_path: str = None):
    plt.figure(figsize=(12, 4))

    # 训练损失
    plt.subplot(1, 2, 1)
    plt.plot(trainer.train_losses, label='训练损失')
    if trainer.val_losses:
        plt.plot(trainer.val_losses, label='验证损失')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('训练损失曲线')
    plt.legend()
    plt.grid(True)

    # 学习率
    plt.subplot(1, 2, 2)
    plt.xlabel('Epoch')
    plt.ylabel('Learning Rate')
    plt.title('学习率变化曲线')
    plt.grid(True)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"训练曲线已保存: {save_path}")

    plt.show()

# 计算困惑度
def caculate_perplexity(loss: float) -> float:
    return torch.exp(torch.tensor(loss)).item()