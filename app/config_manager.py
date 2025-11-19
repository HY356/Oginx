"""
配置管理器
"""

import yaml
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or os.getenv('CONFIG_FILE', 'config/app.yaml')
        self.config = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
                self._load_default_config()
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            
            logger.info(f"配置文件加载成功: {self.config_file}")
            
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            self._load_default_config()
    
    def _load_default_config(self):
        """加载默认配置"""
        self.config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8080,
                'workers': 1
            },
            'database': {
                'url': 'mysql+pymysql://root:hedong2018@172.21.32.3:3306/hetengwx',
                'pool_size': 10,
                'max_overflow': 20,
                'pool_recycle': 3600
            },
            'load_balancer': {
                'health_check_timeout': 1.0,
                'config_cache_ttl': 60,
                'max_retries': 3
            },
            'logging': {
                'level': 'INFO',
                'enable_request_log': True,
                'enable_error_log': True,
                'enable_performance_log': True,
                'enable_health_log': True,
                'log_format': 'detailed',
                'log_dir': 'logs',
                'real_time_flush': True,
                'flush_interval': 0
            }
        }
        logger.info("使用默认配置")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self.config.get('server', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self.config.get('database', {})
    
    def get_load_balancer_config(self) -> Dict[str, Any]:
        """获取负载均衡配置"""
        return self.config.get('load_balancer', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config.get('logging', {})
    
    def reload(self):
        """重新加载配置"""
        logger.info("重新加载配置文件...")
        self._load_config()
        logger.info("配置文件重新加载完成")
    
    def __getitem__(self, key: str):
        """支持字典式访问"""
        return self.get(key)
    
    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return self.get(key) is not None

# 全局配置管理器实例
config_manager = ConfigManager()
