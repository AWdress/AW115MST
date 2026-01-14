"""
配置管理模块
负责读取、保存和管理配置文件
"""

import yaml
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化配置管理器
        
        :param config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        return self.config
    
    def save_config(self, config: Dict[str, Any] = None) -> None:
        """
        保存配置到文件
        
        :param config: 配置字典，如果为None则保存当前配置
        """
        if config is not None:
            self.config = config
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置项（支持点号分隔的路径）
        
        :param key_path: 配置键路径，如 "p115.cookies_file"
        :param default: 默认值
        :return: 配置值
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        设置配置项
        
        :param key_path: 配置键路径
        :param value: 配置值
        """
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def get_p115_config(self) -> Dict[str, Any]:
        """获取115配置"""
        return self.config.get('p115', {})
    
    def get_file_processing_config(self) -> Dict[str, Any]:
        """获取文件处理配置"""
        return self.config.get('file_processing', {})
    
    def get_performance_config(self) -> Dict[str, Any]:
        """获取性能配置"""
        return self.config.get('performance', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config.get('logging', {})
    
    def get_checkpoint_config(self) -> Dict[str, Any]:
        """获取断点续传配置"""
        return self.config.get('checkpoint', {})
