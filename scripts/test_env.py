import torch
import subprocess

print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA可用: {torch.cuda.is_available()}")
print(f"CUDA版本: {torch.version.cuda}")
print(f"cuDNN版本: {torch.backends.cudnn.version()}")
print(f"cuDNN启用: {torch.backends.cudnn.enabled}")

# 查看 CUDA 库路径
if torch.cuda.is_available():
    print(f"GPU型号: {torch.cuda.get_device_name(0)}")
    
    # 查看 cuBLAS 版本信息
    try:
        # 执行 nvcc 命令查看 CUDA 版本
        result = subprocess.run(['nvcc', '--version'], capture_output=True, text=True)
        print("NVCC版本:", result.stdout.split('\n')[-2] if result.stdout else "未找到")
    except:
        print("无法获取 NVCC 版本")