# scripts/prepare_pretrain_data.py
import json
import os
import glob
from pathlib import Path
import random
from tqdm import tqdm
import sys
import re
import psutil
import gc
import time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from model.tokenizer import tokenizer
from configs import MODEL_CONFIG

class PretrainDataPreprocessor:
    """预训练数据预处理器 - 优化内存管理"""
    
    def __init__(self, max_seq_length=MODEL_CONFIG.max_seq_length, memory_limit_gb=4):
        self.max_seq_length = max_seq_length
        self.tokenizer = tokenizer
        self.memory_limit = memory_limit_gb * 1024 * 1024 * 1024
        self.memory_warning_count = 0
        self.last_gc_time = time.time()
        
    def check_memory(self, force_gc=False):
        """检查内存使用情况，智能GC"""
        memory_usage = psutil.Process().memory_info().rss
        memory_gb = memory_usage / 1024 / 1024 / 1024
        
        if memory_usage > self.memory_limit:
            self.memory_warning_count += 1
            
            # 只在第一次和每10次警告时显示
            if self.memory_warning_count == 1 or self.memory_warning_count % 10 == 0:
                print(f"\n⚠️ 内存使用: {memory_gb:.1f} GB (警告 #{self.memory_warning_count})")
            
            # 强制GC
            if force_gc or memory_usage > self.memory_limit * 1.2:
                gc.collect()
                if hasattr(gc, 'garbage'):
                    gc.garbage.clear()
                
                # 记录GC时间
                self.last_gc_time = time.time()
                
                if self.memory_warning_count % 10 == 0:
                    print(f"  执行垃圾回收，释放内存")
            
            return True
        
        # 定期GC（每5分钟）
        if time.time() - self.last_gc_time > 300:  # 5分钟
            gc.collect()
            self.last_gc_time = time.time()
            
        return False
    
    def process_cluecorpus_files(self, input_dir, output_path, sample_ratio=1.0):
        """处理多个CLUECorpus文件 - 优化内存"""
        print(f"处理 CLUECorpus 目录: {input_dir}")
        
        json_files = glob.glob(os.path.join(input_dir, "*.json"))
        print(f"找到 {len(json_files)} 个CLUECorpus文件")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        total_samples = 0
        failed_files = []
        
        for file_path in tqdm(json_files, desc="处理CLUECorpus文件"):
            try:
                file_samples = self._process_single_cluecorpus_stream(file_path, output_path, sample_ratio)
                total_samples += file_samples
                print(f"\n当前总样本数: {total_samples:,}")
            except Exception as e:
                print(f"\n❌ 处理文件 {os.path.basename(file_path)} 时出错: {e}")
                failed_files.append(os.path.basename(file_path))
            
            # 每个文件处理后强制GC
            gc.collect()
        
        print(f"\nCLUECorpus处理完成，总样本数: {total_samples:,}")
        if failed_files:
            print(f"失败的文件: {failed_files}")
    
    def _process_single_cluecorpus_stream(self, file_path, output_path, sample_ratio):
        """优化内存的流式处理"""
        samples_processed = 0
        
        # 使用更小的批处理大小
        batch_size = 5000  # 从10000减小到5000
        batch_samples = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 逐行读取，而不是一次性加载全部
                data = json.load(f)
                
                # 使用迭代器而不是切片
                for item in tqdm(data, desc=f"处理 {os.path.basename(file_path)}", leave=False):
                    if random.random() > sample_ratio:
                        continue
                    
                    text = item.get('text', '')
                    if len(text) < 10:
                        continue
                    
                    # 限制文本长度，避免处理过长的文本
                    if len(text) > 5000:  # 如果文本太长，截断
                        text = text[:5000]
                    
                    sentences = self._split_sentences(text)
                    
                    for sentence in sentences:
                        if len(sentence) < 5 or len(sentence) > 500:  # 过滤过长或过短的句子
                            continue
                        
                        token_ids = self.tokenizer.encode(sentence)
                        
                        if len(token_ids) > self.max_seq_length:
                            token_ids = token_ids[:self.max_seq_length]
                        
                        batch_samples.append({
                            'text': sentence,
                            'token_ids': token_ids,
                            'source': 'cluecorpus'
                        })
                        
                        samples_processed += 1
                        
                        # 达到批量大小时写入并清空
                        if len(batch_samples) >= batch_size:
                            self._append_to_file(output_path, batch_samples)
                            batch_samples = []
                            
                            # 检查内存
                            self.check_memory(force_gc=True)
                            
                            # 可选：减少进度条更新频率
                            if samples_processed % 50000 == 0:
                                print(f"\n  已处理 {samples_processed:,} 条")
                
                # 写入剩余样本
                if batch_samples:
                    self._append_to_file(output_path, batch_samples)
                        
        except Exception as e:
            print(f"\n  详细错误: {e}")
            raise
        
        return samples_processed
    
    def process_lccc_files(self, input_dir, output_path, sample_ratio=1.0):
        """处理LCCC文件 - 优化内存"""
        print(f"处理 LCCC 目录: {input_dir}")
        
        json_files = glob.glob(os.path.join(input_dir, "*.json"))
        print(f"找到 {len(json_files)} 个LCCC文件")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        total_samples = 0
        for file_path in tqdm(json_files, desc="处理LCCC文件"):
            file_samples = self._process_single_lccc_stream(file_path, output_path, sample_ratio)
            total_samples += file_samples
            print(f"\n当前总样本数: {total_samples:,}")
            
            gc.collect()
    
    def _process_single_lccc_stream(self, file_path, output_path, sample_ratio):
        """优化内存的LCCC处理"""
        samples_processed = 0
        
        batch_size = 5000
        batch_samples = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                conversations = json.load(f)
                
                for conversation in tqdm(conversations, desc=f"处理 {os.path.basename(file_path)}", leave=False):
                    if random.random() > sample_ratio:
                        continue
                    
                    # 限制对话长度
                    if len(conversation) > 20:  # 如果对话太长，只取前20句
                        conversation = conversation[:20]
                    
                    cleaned_utterances = []
                    for utterance in conversation:
                        cleaned = re.sub(r'\s+', '', utterance)
                        if cleaned and len(cleaned) < 200:  # 过滤过长的句子
                            cleaned_utterances.append(cleaned)
                    
                    if not cleaned_utterances:
                        continue
                    
                    full_text = " ".join(cleaned_utterances)
                    
                    if len(full_text) < 10 or len(full_text) > 2000:  # 过滤过长对话
                        continue
                    
                    sentences = self._split_sentences(full_text)
                    
                    for sentence in sentences:
                        if len(sentence) < 5 or len(sentence) > 500:
                            continue
                        
                        sentence = re.sub(r'\s+', '', sentence)
                        
                        token_ids = self.tokenizer.encode(sentence)
                        
                        if len(token_ids) > self.max_seq_length:
                            token_ids = token_ids[:self.max_seq_length]
                        
                        batch_samples.append({
                            'text': sentence,
                            'token_ids': token_ids,
                            'source': 'lccc'
                        })
                        
                        samples_processed += 1
                        
                        if len(batch_samples) >= batch_size:
                            self._append_to_file(output_path, batch_samples)
                            batch_samples = []
                            self.check_memory(force_gc=True)
                
                if batch_samples:
                    self._append_to_file(output_path, batch_samples)
                        
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
        
        return samples_processed
    
    def _append_to_file(self, file_path, samples):
        """追加样本到文件，添加进度提示"""
        with open(file_path, 'a', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        # 只在重要时刻显示提示
        if len(samples) >= 5000:
            file_size = os.path.getsize(file_path) / 1024 / 1024
            print(f"\n💾 已保存 {len(samples)} 个样本，当前文件大小: {file_size:.1f} MB")
    
    def _split_sentences(self, text):
        """简单分句"""
        sentences = re.split('[。！？!?\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

def main():
    """主函数"""
    print("="*60)
    print("开始数据预处理")
    print("="*60)
    
    # 设置内存限制为6GB（根据你的系统调整）
    preprocessor = PretrainDataPreprocessor(memory_limit_gb=6)
    
    # 检查系统内存
    total_memory = psutil.virtual_memory().total / 1024 / 1024 / 1024
    available_memory = psutil.virtual_memory().available / 1024 / 1024 / 1024
    print(f"系统总内存: {total_memory:.1f} GB")
    print(f"可用内存: {available_memory:.1f} GB")
    
    base_dir = "llm/aronaLM/data"
    
    # 1. 处理CLUECorpus
    clue_input_dir = os.path.join(base_dir, "raw", "cluecorpus2020")
    clue_output = os.path.join(base_dir, "processed", "cluecorpus.jsonl")
    
    if os.path.exists(clue_input_dir):
        print("\n" + "="*40)
        print("处理CLUECorpus...")
        print("="*40)
        preprocessor.process_cluecorpus_files(
            clue_input_dir,
            clue_output,
            sample_ratio=1.0
        )
    
    # 2. 处理LCCC
    # lccc_input_dir = os.path.join(base_dir, "raw", "lccc")
    # lccc_output = os.path.join(base_dir, "processed", "lccc.jsonl")
    
    # if os.path.exists(lccc_input_dir):
    #     print("\n" + "="*40)
    #     print("处理LCCC...")
    #     print("="*40)
    #     preprocessor.process_lccc_files(
    #         lccc_input_dir,
    #         lccc_output,
    #         sample_ratio=1.0
    #     )
    
    print("\n" + "="*60)
    print("✅ 数据处理完成！")
    print("="*60)

if __name__ == "__main__":
    main()