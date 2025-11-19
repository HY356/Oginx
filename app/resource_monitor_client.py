"""
资源监控客户端模块
用于调用资源监控服务检查服务器资源是否充足
"""

import os
import httpx
import logging
import time
from urllib.parse import urlparse
from typing import Dict, Any, Optional, Tuple
from .resource_cache_config import (
    SAME_MODEL_INTERVAL,
    MODEL_USAGE_WINDOW
)

logger = logging.getLogger(__name__)

# 资源监控服务端口配置
RESOURCE_MONITOR_CPU_PORT = int(os.getenv('RESOURCE_MONITOR_CPU_PORT', '8005'))
RESOURCE_MONITOR_GPU_PORT = int(os.getenv('RESOURCE_MONITOR_GPU_PORT', '8006'))

class ResourceMonitorClient:
    """资源监控客户端"""
    
    def __init__(self, resource_monitor_port: int = None):
        """
        初始化资源监控客户端
        
        Args:
            resource_monitor_port: 资源监控服务端口（已废弃，使用环境变量配置）
        """
        self.resource_monitor_port = resource_monitor_port
        self.logger = logging.getLogger(__name__)
        
        # 模型使用历史跟踪
        self._model_usage_history: Dict[str, float] = {}
    
    def _should_skip_resource_check(self, server_url: str, model_name: str) -> bool:
        """检查是否应该跳过资源检查（基于模型并发感知）"""
        usage_key = f"{server_url}:{model_name}"
        last_usage_time = self._model_usage_history.get(usage_key, 0)
        current_time = time.time()
        
        # 如果相同模型在指定时间间隔内使用过，跳过资源检查
        if (current_time - last_usage_time) < SAME_MODEL_INTERVAL:
            self.logger.debug(f"跳过资源检查: {server_url} 模型 {model_name} 在 {SAME_MODEL_INTERVAL} 秒内使用过")
            return True
        
        return False
    
    def _track_model_usage(self, server_url: str, model_name: str):
        """记录模型使用历史"""
        usage_key = f"{server_url}:{model_name}"
        current_time = time.time()
        self._model_usage_history[usage_key] = current_time
        
        # 清理过期的使用历史（超过窗口时间的记录）
        expired_keys = []
        for key, timestamp in self._model_usage_history.items():
            if (current_time - timestamp) > MODEL_USAGE_WINDOW:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._model_usage_history[key]
        
        self.logger.debug(f"记录模型使用: {usage_key} 在 {current_time}")
    
    def _convert_url_to_resource_monitor(self, server_url: str, server_type: str = "CPU") -> str:
        """将服务器URL转换为资源监控服务URL"""
        try:
            parsed = urlparse(server_url)
            # 根据服务器类型选择不同端口
            if server_type.upper() == "GPU":
                port = RESOURCE_MONITOR_GPU_PORT
            else:
                port = RESOURCE_MONITOR_CPU_PORT
            
            resource_monitor_url = f"{parsed.scheme}://{parsed.hostname}:{port}"
            return resource_monitor_url
        except Exception as e:
            logger.error(f"URL转换失败: {server_url}, 错误: {e}")
            return None
    
    async def check_server_resource(self, server_url: str, server_type: str, 
                                  performance_gb: int, model_name: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        检查服务器资源是否充足(仅模型并发感知)
        
        Args:
            server_url: 原始服务器URL
            server_type: CPU 或 GPU
            performance_gb: 需要的性能(GB)
            model_name: 模型名称(用于并发检测)
            
        Returns:
            (is_sufficient, resource_info): 资源是否充足和详细信息
        """
        # 1. 模型并发检测
        if model_name and self._should_skip_resource_check(server_url, model_name):
            self.logger.info(f"跳过资源检查: {server_url} 模型 {model_name} 可能正在使用中")
            return True, {"skipped": True, "reason": "same_model_concurrent"}
        
        # 2. 直接进行资源检查
        resource_monitor_url = self._convert_url_to_resource_monitor(server_url, server_type)
        if not resource_monitor_url:
            raise Exception(f"无法转换资源监控URL: {server_url}")
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 调用资源检查接口
                check_url = f"{resource_monitor_url}/resource-check"
                payload = {
                    "type": server_type,
                    "performance": performance_gb
                }
                
                port = RESOURCE_MONITOR_GPU_PORT if server_type.upper() == "GPU" else RESOURCE_MONITOR_CPU_PORT
                self.logger.info(f"🔍 调用资源监控服务: {check_url} (端口: {port})")
                self.logger.info(f"📋 检查参数: 类型={server_type}, 需求={performance_gb}GB, 模型={model_name}")
                
                response = await client.post(
                    check_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        data = result.get('data', {})
                        is_sufficient = data.get('sufficient', False)
                        
                        # 详细记录资源信息
                        available_gb = data.get('available_gb', 0)
                        total_gb = data.get('total_gb', 0)
                        usage_percent = data.get('usage_percent', 0)
                        
                        self.logger.info(f"📊 资源监控响应: 服务器={server_url}")
                        self.logger.info(f"   ├─ 类型: {server_type}")
                        self.logger.info(f"   ├─ 总容量: {total_gb:.1f}GB")
                        self.logger.info(f"   ├─ 可用容量: {available_gb:.1f}GB")
                        self.logger.info(f"   ├─ 使用率: {usage_percent:.1f}%")
                        self.logger.info(f"   ├─ 模型需求: {performance_gb}GB")
                        self.logger.info(f"   └─ 资源充足: {'✅ 是' if is_sufficient else '❌ 否'}")
                        
                        # 记录模型使用历史
                        if model_name:
                            self._track_model_usage(server_url, model_name)
                        
                        return is_sufficient, data
                    else:
                        error_msg = result.get('message', '未知错误')
                        self.logger.warning(f"资源检查失败: {error_msg}")
                        return False, {"error": error_msg}
                else:
                    error_msg = f"资源监控服务返回错误状态码: {response.status_code}"
                    logger.warning(error_msg)
                    return False, {"error": error_msg}
                    
        except httpx.TimeoutException:
            error_msg = f"资源监控服务超时: {resource_monitor_url}"
            logger.warning(error_msg)
            return False, {"error": error_msg}
            
        except httpx.RequestError as e:
            error_msg = f"资源监控服务连接失败: {str(e)}"
            logger.warning(error_msg)
            return False, {"error": error_msg}
            
        except Exception as e:
            error_msg = f"资源检查异常: {str(e)}"
            logger.error(error_msg)
            return False, {"error": error_msg}
    
    def get_model_usage_stats(self) -> Dict[str, Any]:
        """获取模型使用统计信息"""
        current_time = time.time()
        active_usage_count = 0
        
        for timestamp in self._model_usage_history.values():
            if (current_time - timestamp) < MODEL_USAGE_WINDOW:
                active_usage_count += 1
        
        return {
            'total_model_usage_entries': len(self._model_usage_history),
            'active_usage_entries': active_usage_count,
            'same_model_interval': SAME_MODEL_INTERVAL,
            'model_usage_window': MODEL_USAGE_WINDOW
        }
    
    def clear_model_usage_history(self):
        """清空模型使用历史"""
        self._model_usage_history.clear()
        self.logger.info("已清空模型使用历史")
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置信息"""
        return {
            'resource_monitor_port': self.resource_monitor_port,
            'same_model_interval': SAME_MODEL_INTERVAL,
            'model_usage_window': MODEL_USAGE_WINDOW
        }
    
    async def get_memory_info(self, server_url: str, server_type: str = "CPU") -> Optional[Dict[str, Any]]:
        """获取服务器内存信息"""
        resource_monitor_url = self._convert_url_to_resource_monitor(server_url, server_type)
        if not resource_monitor_url:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{resource_monitor_url}/memory")
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        return result.get('data')
                        
        except Exception as e:
            logger.warning(f"获取内存信息失败: {server_url}, 错误: {e}")
        
        return None
    
    async def get_gpu_memory_info(self, server_url: str, server_type: str = "GPU") -> Optional[Dict[str, Any]]:
        """获取服务器GPU显存信息"""
        resource_monitor_url = self._convert_url_to_resource_monitor(server_url, server_type)
        if not resource_monitor_url:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{resource_monitor_url}/gpu-memory")
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        return result.get('data')
                        
        except Exception as e:
            logger.warning(f"获取GPU显存信息失败: {server_url}, 错误: {e}")
        
        return None

# 全局资源监控客户端实例
resource_monitor_client = ResourceMonitorClient()
