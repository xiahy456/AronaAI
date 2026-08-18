# convert_fonts.py
import os
import sys
from fontTools import ttLib
import brotli

def convert_woff2_to_ttf(woff2_path, ttf_path):
    """将 WOFF2 转换为 TTF"""
    try:
        # 方法1: 使用 fontTools 的 woff2 模块
        from fontTools.ttLib import woff2
        
        # 读取 WOFF2 文件
        with open(woff2_path, 'rb') as f:
            woff2_data = f.read()
        
        # 解压缩 WOFF2 到 TTF 文件
        with open(ttf_path, 'wb') as f:
            woff2.decompress(woff2_data, f)
        
        print(f"✓ Converted: {os.path.basename(woff2_path)} -> {os.path.basename(ttf_path)}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to convert {os.path.basename(woff2_path)}: {e}")
        return False

def convert_all_woff2_in_directory(directory):
    """转换目录下所有 WOFF2 文件"""
    converted_count = 0
    failed_count = 0
    
    # 获取所有 WOFF2 文件
    woff2_files = [f for f in os.listdir(directory) if f.endswith('.woff2')]
    
    print(f"Found {len(woff2_files)} WOFF2 files to convert")
    print("=" * 50)
    
    for filename in woff2_files:
        woff2_path = os.path.join(directory, filename)
        ttf_filename = filename.replace('.woff2', '.ttf')
        ttf_path = os.path.join(directory, ttf_filename)
        
        # 跳过已存在的 TTF 文件
        if os.path.exists(ttf_path):
            print(f"⊙ Skip (already exists): {ttf_filename}")
            continue
        
        if convert_woff2_to_ttf(woff2_path, ttf_path):
            converted_count += 1
        else:
            failed_count += 1
    
    print("=" * 50)
    print(f"Conversion complete: {converted_count} converted, {failed_count} failed")
    return converted_count > 0

if __name__ == '__main__':
    # 字体目录路径
    font_dir = r"D:/Code/projects/Arona/arona-ai/font/Blueaka"
    
    if not os.path.exists(font_dir):
        print(f"Directory not found: {font_dir}")
        sys.exit(1)
    
    convert_all_woff2_in_directory(font_dir)