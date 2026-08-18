import os
import sys
from fontTools.merge import Merger
from fontTools.ttLib import TTFont

def merge_all_ttf(directory, output_name="merged.ttf", verbose=True):
    """合并目录下所有 TTF 文件，并检查 units per em"""
    
    # 收集所有 ttf 文件
    ttf_files = [f for f in os.listdir(directory) if f.lower().endswith('.ttf')]
    ttf_paths = [os.path.join(directory, f) for f in ttf_files]
    
    if len(ttf_paths) < 2:
        print("至少需要 2 个 TTF 文件才能合并")
        return False
    
    # 检查 units per em 一致性
    units_per_em_list = []
    for path in ttf_paths:
        font = TTFont(path)
        upem = font['head'].unitsPerEm
        units_per_em_list.append(upem)
        font.close()
    
    if len(set(units_per_em_list)) > 1:
        print("警告：发现不同的 units per em 值:")
        for path, upem in zip(ttf_paths, units_per_em_list):
            print(f"  {os.path.basename(path)}: {upem}")
        print("合并后可能出现大小问题，建议先统一度量标准")
    
    # 执行合并
    merger = Merger()
    try:
        if verbose:
            print(f"正在合并 {len(ttf_paths)} 个字体文件...")
        merged = merger.merge(ttf_paths)
        output_path = os.path.join(directory, output_name)
        merged.save(output_path)
        if verbose:
            print(f"合并成功: {output_path}")
        return True
    except Exception as e:
        print(f"合并失败: {e}")
        return False
    finally:
        merger.close()

# 使用
if __name__ == "__main__":
    # 替换为你的目录路径
    font_dir = "D:/Code/projects/Arona/arona-ai/font/Blueaka/"
    merge_all_ttf(font_dir, "Blueaka_comp.ttf")