"""
日志管理器
"""

import logging
import logging.handlers
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
try:
    from .config_manager import config_manager
except ImportError:
    from app.config_manager import config_manager

class FlushingFileHandler(logging.handlers.RotatingFileHandler):
    """支持实时刷新的文件处理器"""
    
    def __init__(self, *args, **kwargs):
        self.real_time_flush = kwargs.pop('real_time_flush', True)
        super().__init__(*args, **kwargs)
    
    def emit(self, record):
        """发出日志记录并根据配置进行刷新"""
        super().emit(record)
        if self.real_time_flush:
            self.flush()

class JSONFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 添加额外的字段
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'server_url'):
            log_entry['server_url'] = record.server_url
        if hasattr(record, 'model_name'):
            log_entry['model_name'] = record.model_name
        if hasattr(record, 'response_time'):
            log_entry['response_time'] = record.response_time
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
        
        return json.dumps(log_entry, ensure_ascii=False)

class LoggingManager:
    """日志管理器"""
    
    def __init__(self):
        self.log_dir = Path(config_manager.get('logging.log_dir', 'logs'))
        self.log_dir.mkdir(exist_ok=True)
        self.handlers = []  # 保存所有文件处理器的引用
        self.flush_thread = None
        self.flush_stop_event = threading.Event()
        self._setup_loggers()
        self._start_periodic_flush()
    
    def _setup_loggers(self):
        """设置各种日志记录器"""
        log_level = getattr(logging, config_manager.get('logging.level', 'INFO').upper())
        log_format = config_manager.get('logging.log_format', 'detailed')
        
        # 主应用日志
        self._setup_app_logger(log_level, log_format)
        
        # 请求日志
        if config_manager.get('logging.enable_request_log', True):
            self._setup_request_logger()
        
        # 错误日志
        if config_manager.get('logging.enable_error_log', True):
            self._setup_error_logger()
        
        # 性能日志
        if config_manager.get('logging.enable_performance_log', True):
            self._setup_performance_logger()
        
        # 健康检查日志
        if config_manager.get('logging.enable_health_log', True):
            self._setup_health_logger()
    
    def _setup_app_logger(self, log_level, log_format):
        """设置应用程序日志"""
        logger = logging.getLogger()
        logger.setLevel(log_level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        
        if log_format == 'simple':
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器
        real_time_flush = config_manager.get('logging.real_time_flush', True)
        file_handler = FlushingFileHandler(
            self.log_dir / 'app.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8',
            real_time_flush=real_time_flush
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        self.handlers.append(file_handler)
    
    def _setup_request_logger(self):
        """设置请求日志"""
        logger = logging.getLogger('request')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        real_time_flush = config_manager.get('logging.real_time_flush', True)
        handler = FlushingFileHandler(
            self.log_dir / 'request.log',
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10,
            encoding='utf-8',
            real_time_flush=real_time_flush
        )
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        self.handlers.append(handler)
    
    def _setup_error_logger(self):
        """设置错误日志"""
        logger = logging.getLogger('error')
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        
        real_time_flush = config_manager.get('logging.real_time_flush', True)
        handler = FlushingFileHandler(
            self.log_dir / 'error.log',
            maxBytes=20*1024*1024,  # 20MB
            backupCount=10,
            encoding='utf-8',
            real_time_flush=real_time_flush
        )
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        self.handlers.append(handler)
    
    def _setup_performance_logger(self):
        """设置性能日志"""
        logger = logging.getLogger('performance')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        real_time_flush = config_manager.get('logging.real_time_flush', True)
        handler = FlushingFileHandler(
            self.log_dir / 'performance.log',
            maxBytes=20*1024*1024,  # 20MB
            backupCount=5,
            encoding='utf-8',
            real_time_flush=real_time_flush
        )
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        self.handlers.append(handler)
    
    def _setup_health_logger(self):
        """设置健康检查日志"""
        logger = logging.getLogger('health')
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        real_time_flush = config_manager.get('logging.real_time_flush', True)
        handler = FlushingFileHandler(
            self.log_dir / 'health.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3,
            encoding='utf-8',
            real_time_flush=real_time_flush
        )
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        self.handlers.append(handler)
    
    def log_request(self, request_id: str, method: str, url: str, 
                   model_name: str = None, server_url: str = None, 
                   response_time: float = None, status_code: int = None,
                   message: str = None):
        """记录请求日志"""
        logger = logging.getLogger('request')
        extra = {
            'request_id': request_id,
            'method': method,
            'url': url
        }
        if model_name:
            extra['model_name'] = model_name
        if server_url:
            extra['server_url'] = server_url
        if response_time is not None:
            extra['response_time'] = response_time
        if status_code is not None:
            extra['status_code'] = status_code
        
        logger.info(message or f"{method} {url}", extra=extra)
    
    def log_error(self, error: Exception, request_id: str = None, 
                 server_url: str = None, model_name: str = None):
        """记录错误日志"""
        logger = logging.getLogger('error')
        extra = {
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        if request_id:
            extra['request_id'] = request_id
        if server_url:
            extra['server_url'] = server_url
        if model_name:
            extra['model_name'] = model_name
        
        logger.error(f"错误: {error}", extra=extra, exc_info=True)
    
    def log_performance(self, operation: str, duration: float, 
                       server_url: str = None, model_name: str = None,
                       request_id: str = None):
        """记录性能日志"""
        logger = logging.getLogger('performance')
        extra = {
            'operation': operation,
            'duration': duration
        }
        if server_url:
            extra['server_url'] = server_url
        if model_name:
            extra['model_name'] = model_name
        if request_id:
            extra['request_id'] = request_id
        
        logger.info(f"性能: {operation} 耗时 {duration:.3f}s", extra=extra)
    
    def log_health_check(self, server_url: str, status: str, 
                        response_time: float = None, error: str = None):
        """记录健康检查日志"""
        logger = logging.getLogger('health')
        extra = {
            'server_url': server_url,
            'health_status': status
        }
        if response_time is not None:
            extra['response_time'] = response_time
        if error:
            extra['error'] = error
        
        message = f"健康检查: {server_url} - {status}"
        if response_time is not None:
            message += f" ({response_time:.3f}s)"
        
        if status == 'healthy':
            logger.info(message, extra=extra)
        else:
            logger.warning(message, extra=extra)
    
    def _start_periodic_flush(self):
        """启动定期刷新线程"""
        flush_interval = config_manager.get('logging.flush_interval', 1)
        real_time_flush = config_manager.get('logging.real_time_flush', True)
        
        # 如果启用了实时刷新且间隔大于0，则启动定期刷新线程
        if real_time_flush and flush_interval > 0:
            self.flush_thread = threading.Thread(
                target=self._periodic_flush_worker,
                args=(flush_interval,),
                daemon=True
            )
            self.flush_thread.start()
    
    def _periodic_flush_worker(self, interval):
        """定期刷新工作线程"""
        while not self.flush_stop_event.wait(interval):
            try:
                for handler in self.handlers:
                    if hasattr(handler, 'flush'):
                        handler.flush()
            except Exception as e:
                # 避免在刷新过程中产生日志循环
                print(f"日志刷新错误: {e}")
    
    def force_flush_all(self):
        """强制刷新所有日志处理器"""
        for handler in self.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
    
    def stop_periodic_flush(self):
        """停止定期刷新线程"""
        if self.flush_thread and self.flush_thread.is_alive():
            self.flush_stop_event.set()
            self.flush_thread.join(timeout=5)
    
    def __del__(self):
        """析构函数，确保清理资源"""
        self.stop_periodic_flush()

# 全局日志管理器实例
logging_manager = LoggingManager()
