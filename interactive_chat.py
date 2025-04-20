import json
import os
from openai import OpenAI
import sys
from model_manager import ModelManager
import requests

# OpenAI 代理配置
OPENAI_PROXY = {
    "http": "http://testai:testai@192.168.1.7:6666",
    "https": "http://testai:testai@192.168.1.7:6666"
}

class InteractiveChat:
    def __init__(self, config_path=None):
        self.model_manager = ModelManager(config_path)
        self.current_model = "qwen2.5:3b"  # 默认模型改为qwen2.5:3b
        self.current_model_config = self.model_manager.get_model_config(self.current_model)
        self.client = None
        
        # 如果是OpenAI模型，初始化OpenAI客户端
        if self.current_model_config.get("provider") == "openai":
            os.environ["HTTP_PROXY"] = OPENAI_PROXY["http"]
            os.environ["HTTPS_PROXY"] = OPENAI_PROXY["https"]
            self.client = OpenAI(api_key=self.current_model_config["api_key"])

    def set_model(self, model_key):
        # 清理之前可能设置的代理
        if "HTTP_PROXY" in os.environ:
            del os.environ["HTTP_PROXY"]
        if "HTTPS_PROXY" in os.environ:
            del os.environ["HTTPS_PROXY"]
            
        model_config = self.model_manager.get_model_config(model_key)
        if model_config:
            self.current_model = model_key
            self.current_model_config = model_config
            
            # 如果切换到OpenAI模型，更新客户端和代理
            if model_config.get("provider") == "openai":
                os.environ["HTTP_PROXY"] = OPENAI_PROXY["http"]
                os.environ["HTTPS_PROXY"] = OPENAI_PROXY["https"]
                self.client = OpenAI(api_key=model_config["api_key"])
            else:
                self.client = None
            
            print(f"模型已切换到: {model_key}")
        else:
            print(f"未找到模型 {model_key}")
            self.model_manager.list_all_models()

    def chat(self, message):
        try:
            # OpenAI模型处理
            if self.current_model_config.get("provider") == "openai":
                model_config = self.current_model_config["config"]
                response = self.client.chat.completions.create(
                    model=model_config["name"],
                    messages=[{"role": "user", "content": message}],
                    # temperature=model_config["temperature"],
                    # max_tokens=model_config["max_tokens"]
                )
                return response.choices[0].message.content
            
            # 本地模型处理
            elif self.current_model_config["type"] == "local_llm":
                model_config = self.current_model_config["config"]
                response = requests.post(
                    f"{model_config['base_url']}/api/chat",
                    json={
                        "model": model_config["model_name"],
                        "messages": [{"role": "user", "content": message}],
                        "temperature": model_config.get("temperature", 0.7),
                        "stream": False
                    }
                )
                if response.status_code == 200:
                    return response.json()["message"]["content"]
                else:
                    print(f"本地模型请求失败: {response.text}")
                    return None
            
            # Deepseek模型处理
            elif self.current_model_config.get("provider") == "deepseek_v3" or self.current_model_config.get("provider") == "deepseek_r1":
                model_config = self.current_model_config["config"]
                headers = {
                    "Authorization": f"Bearer {model_config['api_key']}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(
                    model_config["base_url"],
                    json={
                        "model": model_config["model_name"],
                        "messages": [{"role": "user", "content": message}],
                        "temperature": model_config.get("temperature", 0.3),
                        "max_tokens": 4096
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"]
                else:
                    print(f"Deepseek API请求失败: {response.text}")
                    return None
            
            # 阿里云模型处理
            elif self.current_model_config.get("provider") == "aliyun":
                model_config = self.current_model_config["config"]
                client = OpenAI(
                    api_key=model_config["api_key"],
                    base_url=model_config["base_url"]
                )
                response = client.chat.completions.create(
                    model=model_config["model_name"],
                    messages=[{"role": "user", "content": message}],
                    temperature=model_config.get("temperature", 0.3)
                )
                return response.choices[0].message.content
            
            # 其他API模型处理
            else:
                print(f"暂不支持 {self.current_model_config.get('provider', '未知')} 类型的模型")
                return None
                
        except Exception as e:
            print(f"聊天过程中出错: {e}")
            return None

def main():
    try:
        chat = InteractiveChat()
        print("\n=== Interactive Chat ===")
        print("当前使用的模型:", chat.current_model)
        chat.model_manager.list_all_models()
        print("\n输入 'quit' 退出")
        print("输入 'change_model 模型名' 更换模型")
        print("输入 'list_models' 显示所有可用模型")
        
        while True:
            user_input = input("\n请输入: ").strip()
            
            if user_input.lower() == 'quit':
                break
            
            if user_input.lower() == 'list_models':
                chat.model_manager.list_all_models()
                continue
                
            if user_input.lower().startswith('change_model'):
                try:
                    _, model_name = user_input.split(maxsplit=1)
                    chat.set_model(model_name)
                    continue
                except ValueError:
                    print("使用方式: change_model 模型名")
                    continue
                    
            if user_input:
                response = chat.chat(user_input)
                if response:
                    print("\nAI回复:", response)
    
    except Exception as e:
        print(f"\n程序运行出错: {str(e)}")
        print("请确保:")
        print("1. config.json 文件存在且格式正确")
        print("2. API key 配置正确")
        print("3. 如果使用本地模型，确保Ollama服务正在运行")
        print("4. 如果使用Deepseek模型，确保API key有效且网络正常")
        sys.exit(1)

if __name__ == "__main__":
    main() 