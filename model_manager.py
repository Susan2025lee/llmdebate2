import json
import os
from typing import Dict, List, Optional

class ModelManager:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "config.json")
        
        self.config = self._load_config(config_path)
        self.available_models = self._get_all_models()

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            print(f"尝试加载配置文件: {config_path}")
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            raise

    def _get_all_models(self) -> Dict[str, Dict]:
        """获取所有可用的模型"""
        models = {}
        
        # 获取本地模型
        if "local_llm" in self.config["model"]:
            for model_name, model_config in self.config["model"]["local_llm"].items():
                models[model_name] = {
                    "type": "local_llm",
                    "config": model_config
                }
        
        # 获取API模型
        if "api_llm" in self.config["model"]:
            for provider, provider_config in self.config["model"]["api_llm"].items():
                if provider == "openai":
                    # OpenAI的模型需要特殊处理，因为它有子模型
                    for model_name, model_config in provider_config["models"].items():
                        models[model_name] = {
                            "type": "api_llm",
                            "provider": "openai",
                            "config": model_config,
                            "api_key": provider_config["api_key"]
                        }
                else:
                    # 其他API提供商的模型（如Deepseek）
                    models[provider] = {
                        "type": "api_llm",
                        "provider": provider,
                        "config": provider_config,
                        "api_key": provider_config["api_key"]
                    }
        
        return models

    def get_model_types(self) -> List[str]:
        """获取所有模型类型"""
        return list(set(model["type"] for model in self.available_models.values()))

    def get_models_by_type(self, model_type: str) -> Dict[str, Dict]:
        """获取指定类型的所有模型"""
        return {name: config for name, config in self.available_models.items() 
                if config["type"] == model_type}

    def get_model_config(self, model_name: str) -> Optional[Dict]:
        """获取指定模型的配置"""
        return self.available_models.get(model_name)

    def list_all_models(self) -> None:
        """打印所有可用的模型信息"""
        print("\n=== 可用模型列表 ===")
        
        # 显示本地模型
        local_models = self.get_models_by_type("local_llm")
        if local_models:
            print("\n本地模型:")
            for name, config in local_models.items():
                print(f"  - {name} (base_url: {config['config']['base_url']})")
        
        # 显示API模型
        api_models = self.get_models_by_type("api_llm")
        if api_models:
            print("\nAPI模型:")
            for name, config in api_models.items():
                provider = config.get("provider", "unknown")
                if provider == "openai":
                    print(f"  - {name} (OpenAI)")
                else:
                    model_name = config["config"].get("model_name", "unknown")
                    print(f"  - {name} ({provider}, 模型: {model_name})")

def main():
    """测试ModelManager的功能"""
    try:
        manager = ModelManager()
        manager.list_all_models()
        
        print("\n=== 模型详细信息 ===")
        for model_name in manager.available_models:
            config = manager.get_model_config(model_name)
            print(f"\n{model_name}:")
            print(f"  类型: {config['type']}")
            if "provider" in config:
                print(f"  提供商: {config['provider']}")
            print(f"  配置: {config['config']}")
    
    except Exception as e:
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    main() 