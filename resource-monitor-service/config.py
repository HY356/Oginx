import os

class Config:
    """资源监控服务配置"""
    
    # 服务配置
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8006))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # GPU监控配置
    GPU_TIMEOUT = int(os.getenv('GPU_TIMEOUT', 10))  # nvidia-smi命令超时时间(秒)
    
    # 资源阈值配置
    MEMORY_WARNING_THRESHOLD = float(os.getenv('MEMORY_WARNING_THRESHOLD', 80.0))  # 内存使用率警告阈值(%)
    GPU_WARNING_THRESHOLD = float(os.getenv('GPU_WARNING_THRESHOLD', 80.0))  # GPU显存使用率警告阈值(%)
