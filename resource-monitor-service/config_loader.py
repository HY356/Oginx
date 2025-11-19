"""
配置加载器模块
用于加载和解析资源监控服务配置
"""

import yaml
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_file: str = "config.yaml"):
        """
        初始化配置加载器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, self.config_file)
            
            if not os.path.exists(config_path):
                logger.warning(f"配置文件不存在: {config_path}, 使用默认配置")
                return self._get_default_config()
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"成功加载配置文件: {config_path}")
                return config
                
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}, 使用默认配置")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "device": {
                "type": "CPU",
                "port": {
                    "cpu": 8005,
                    "gpu": 8006
                }
            },
            "service": {
                "host": "0.0.0.0",
                "timeout": 30,
                "log_level": "INFO"
            },
            "monitoring": {
                "memory_threshold": 90,
                "gpu_memory_threshold": 90,
                "check_interval": 5
            },
            "cache": {
                "enabled": True,
                "expire_time": 30
            }
        }
    
    def get_device_type(self) -> str:
        """获取设备类型"""
        return self.config.get("device", {}).get("type", "CPU").upper()
    
    def get_port(self) -> int:
        """根据设备类型获取端口"""
        device_type = self.get_device_type()
        ports = self.config.get("device", {}).get("port", {})
        
        if device_type == "GPU":
            return ports.get("gpu", 8006)
        else:
            return ports.get("cpu", 8005)
    
    def get_host(self) -> str:
        """获取主机地址"""
        return self.config.get("service", {}).get("host", "0.0.0.0")
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return self.config.get("service", {}).get("log_level", "INFO")
    
    def get_timeout(self) -> int:
        """获取超时设置"""
        return self.config.get("service", {}).get("timeout", 30)
    
    def get_memory_threshold(self) -> int:
        """获取内存监控阈值"""
        return self.config.get("monitoring", {}).get("memory_threshold", 90)
    
    def get_gpu_memory_threshold(self) -> int:
        """获取GPU显存监控阈值"""
        return self.config.get("monitoring", {}).get("gpu_memory_threshold", 90)
    
    def get_check_interval(self) -> int:
        """获取监控间隔"""
        return self.config.get("monitoring", {}).get("check_interval", 5)
    
    def is_cache_enabled(self) -> bool:
        """是否启用缓存"""
        return self.config.get("cache", {}).get("enabled", True)
    
    def get_cache_expire_time(self) -> int:
        """获取缓存过期时间"""
        return self.config.get("cache", {}).get("expire_time", 30)
    
    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self.config.copy()
    
    def reload_config(self):
        """重新加载配置"""
        self.config = self._load_config()
        logger.info("配置已重新加载")

# 全局配置加载器实例
config_loader = ConfigLoader()
