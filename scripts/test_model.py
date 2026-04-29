from transformers import AutoModel, AutoTokenizer
model_path = "D:/Code/projects/Arona/arona-ai/models/chatglm3-6b"  # 替换为你的实际模型路径
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModel.from_pretrained(model_path, trust_remote_code=True).cuda()  # 加载到GPU
# 如果是量化加载，参考上面提到的带 load_in_4bit 参数的代码
response, history = model.chat(tokenizer, "你好", history=[])
print(response)