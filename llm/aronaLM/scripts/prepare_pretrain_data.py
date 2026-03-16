# scripts/prepare_pretrain_data.py
import json
import os
import glob
from pathlib import Path
import random
from tqdm import tqdm
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from model.tokenizer import tokenizer
from configs import MODEL_CONFIG

class PretrainDataPreprocessor:
    """预训练数据预处理器 - 支持多文件和多格式"""
    
    def __init__(self, max_seq_length=MODEL_CONFIG.max_seq_len):
        self.max_seq_length = max_seq_length
        self.tokenizer = tokenizer
        
    def process_cluecorpus_files(self, input_dir, output_path, sample_ratio=1.0):
        """处理多个CLUECorpus文件
        
        Args:
            input_dir: 包含多个json文件的目录
            output_path: 输出文件路径
            sample_ratio: 采样比例
        """
        print(f"处理 CLUECorpus 目录: {input_dir}")
        
        # 查找所有json文件
        json_files = glob.glob(os.path.join(input_dir, "*.json"))
        print(f"找到 {len(json_files)} 个CLUECorpus文件")
        
        processed_samples = []
        
        for file_path in tqdm(json_files, desc="处理CLUECorpus文件"):
            file_samples = self._process_single_cluecorpus(file_path, sample_ratio)
            processed_samples.extend(file_samples)
            
            # 定期保存中间结果，防止内存溢出
            if len(processed_samples) >= 100000:
                self._append_to_file(output_path, processed_samples)
                processed_samples = []
        
        # 保存剩余样本
        if processed_samples:
            self._append_to_file(output_path, processed_samples)
        
        print(f"CLUECorpus处理完成，已保存到 {output_path}")
    
    def _process_single_cluecorpus(self, file_path, sample_ratio):
        """处理单个CLUECorpus文件"""
        samples = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # CLUECorpus是json数组格式
                data = json.load(f)
                
                for item in tqdm(data, desc=f"处理 {os.path.basename(file_path)}", leave=False):
                    # 采样
                    if random.random() > sample_ratio:
                        continue
                    
                    text = item.get('text', '')
                    if len(text) < 10:  # 过滤过短文本
                        continue
                    
                    # 分句处理
                    sentences = self._split_sentences(text)
                    
                    for sentence in sentences:
                        if len(sentence) < 5:
                            continue
                        
                        # 编码
                        token_ids = self.tokenizer.encode(sentence)
                        
                        if len(token_ids) > self.max_seq_length:
                            token_ids = token_ids[:self.max_seq_length]
                        
                        samples.append({
                            'text': sentence,
                            'token_ids': token_ids,
                            'source': 'cluecorpus'
                        })
                        
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
        
        return samples
    
    def process_lccc_files(self, input_dir, output_path, sample_ratio=1.0):
        """处理多个LCCC文件
        
        Args:
            input_dir: 包含多个json文件的目录
            output_path: 输出文件路径
            sample_ratio: 采样比例
        """
        print(f"处理 LCCC 目录: {input_dir}")
        
        # 查找所有json文件
        json_files = glob.glob(os.path.join(input_dir, "*.json"))
        print(f"找到 {len(json_files)} 个LCCC文件")
        
        processed_samples = []
        
        for file_path in tqdm(json_files, desc="处理LCCC文件"):
            file_samples = self._process_single_lccc(file_path, sample_ratio)
            processed_samples.extend(file_samples)
            
            # 定期保存中间结果
            if len(processed_samples) >= 100000:
                self._append_to_file(output_path, processed_samples)
                processed_samples = []
        
        # 保存剩余样本
        if processed_samples:
            self._append_to_file(output_path, processed_samples)
        
        print(f"LCCC处理完成，已保存到 {output_path}")
    
    def _process_single_lccc(self, file_path, sample_ratio):
        """处理单个LCCC文件"""
        samples = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # LCCC是对话数组的数组
                conversations = json.load(f)
                
                for conversation in tqdm(conversations, desc=f"处理 {os.path.basename(file_path)}", leave=False):
                    # 采样
                    if random.random() > sample_ratio:
                        continue
                    
                    # 将对话拼成连续的文本
                    full_text = " ".join(conversation)
                    
                    if len(full_text) < 10:
                        continue
                    
                    # 分句处理
                    sentences = self._split_sentences(full_text)
                    
                    for sentence in sentences:
                        if len(sentence) < 5:
                            continue
                        
                        # 注意：LCCC数据中的空格需要保留，但分词器可能不需要
                        # 这里保持原样
                        token_ids = self.tokenizer.encode(sentence)
                        
                        if len(token_ids) > self.max_seq_length:
                            token_ids = token_ids[:self.max_seq_length]
                        
                        samples.append({
                            'text': sentence,
                            'token_ids': token_ids,
                            'source': 'lccc'
                        })
                        
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
        
        return samples
    
    def _append_to_file(self, file_path, samples):
        """追加样本到文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'a', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        print(f"已追加 {len(samples)} 个样本到 {file_path}")
    
    def _split_sentences(self, text):
        """简单分句"""
        import re
        # 中文分句：按句号、问号、感叹号、换行符分割
        sentences = re.split('[。！？!?\n]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def create_train_val_split(self, data_files, output_dir, val_ratio=0.01):
        """创建训练集和验证集
        
        Args:
            data_files: 输入文件列表
            output_dir: 输出目录
            val_ratio: 验证集比例
        """
        print(f"创建训练集/验证集分割...")
        
        all_samples = []
        
        for data_file in data_files:
            if not os.path.exists(data_file):
                print(f"警告: 文件不存在 {data_file}")
                continue
                
            with open(data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    all_samples.append(json.loads(line))
        
        print(f"总样本数: {len(all_samples)}")
        
        # 随机打乱
        random.shuffle(all_samples)
        
        # 分割
        val_size = int(len(all_samples) * val_ratio)
        train_samples = all_samples[val_size:]
        val_samples = all_samples[:val_size]
        
        # 保存
        train_path = os.path.join(output_dir, 'train.jsonl')
        val_path = os.path.join(output_dir, 'val.jsonl')
        
        with open(train_path, 'w', encoding='utf-8') as f:
            for sample in train_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        with open(val_path, 'w', encoding='utf-8') as f:
            for sample in val_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        print(f"训练集: {len(train_samples)} 样本 -> {train_path}")
        print(f"验证集: {len(val_samples)} 样本 -> {val_path}")
        
        return train_path, val_path
    
    def create_sample_data(self, input_path, output_path, num_samples=10000):
        """创建小样本数据用于测试"""
        print(f"创建 {num_samples} 个样本的小数据集...")
        
        samples = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= num_samples:
                    break
                samples.append(json.loads(line))
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        print(f"小数据集已保存到 {output_path}")

def main():
    """主函数"""
    preprocessor = PretrainDataPreprocessor()
    
    # 配置路径
    base_dir = "llm/aronaLM/data"
    
    # 1. 处理CLUECorpus
    clue_input_dir = os.path.join(base_dir, "raw", "cluecorpus2020")
    clue_output = os.path.join(base_dir, "processed", "cluecorpus.jsonl")
    
    if os.path.exists(clue_input_dir):
        preprocessor.process_cluecorpus_files(
            clue_input_dir,
            clue_output,
            sample_ratio=0.1  # 先取10%做实验
        )
    else:
        print(f"警告: CLUECorpus目录不存在 {clue_input_dir}")
    
    # 2. 处理LCCC
    lccc_input_dir = os.path.join(base_dir, "raw", "lccc")
    lccc_output = os.path.join(base_dir, "processed", "lccc.jsonl")
    
    if os.path.exists(lccc_input_dir):
        preprocessor.process_lccc_files(
            lccc_input_dir,
            lccc_output,
            sample_ratio=1.0
        )
    else:
        print(f"警告: LCCC目录不存在 {lccc_input_dir}")
    
    # 3. 合并创建训练/验证集
    processed_files = []
    for f in [clue_output, lccc_output]:
        if os.path.exists(f):
            processed_files.append(f)
    
    if processed_files:
        # 先创建完整的训练/验证集
        train_path, val_path = preprocessor.create_train_val_split(
            processed_files,
            os.path.join(base_dir, "processed"),
            val_ratio=0.01
        )
        
        # 可选：创建小样本数据集用于快速测试
        preprocessor.create_sample_data(
            train_path,
            os.path.join(base_dir, "processed", "train_sample.jsonl"),
            num_samples=10000
        )
    else:
        print("错误: 没有找到处理好的数据文件")

if __name__ == "__main__":
    main()