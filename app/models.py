"""
Pydantic数据模型定义
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ServerConfig(BaseModel):
    """服务器配置模型"""
    virtual_model_name: str = Field(..., description="虚拟模型名称")
    server_url: str = Field(..., description="服务器URL")
    actual_model_name: str = Field(..., description="实际模型名称")
    weight: int = Field(default=100, description="权重")
    priority: int = Field(default=1, description="优先级")
    is_active: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(None, description="描述信息")

class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    timestamp: datetime = Field(..., description="检查时间")
    version: str = Field(..., description="服务版本")
    database: str = Field(..., description="数据库状态")
    servers_count: int = Field(..., description="配置的服务器数量")

class StatusResponse(BaseModel):
    """系统状态响应模型"""
    service_name: str = Field(..., description="服务名称")
    version: str = Field(..., description="版本号")
    uptime: str = Field(..., description="运行时间")
    active_servers: int = Field(..., description="活跃服务器数量")
    total_servers: int = Field(..., description="总服务器数量")
    load_balancer_status: str = Field(..., description="负载均衡器状态")

class OllamaRequest(BaseModel):
    """Ollama请求模型"""
    model: str = Field(..., description="模型名称")
    prompt: Optional[str] = Field(None, description="提示词")
    messages: Optional[List[Dict[str, Any]]] = Field(None, description="对话消息")
    stream: bool = Field(default=False, description="是否流式响应")
    options: Optional[Dict[str, Any]] = Field(None, description="其他选项")

class OllamaResponse(BaseModel):
    """Ollama响应模型"""
    model: str = Field(..., description="模型名称")
    response: Optional[str] = Field(None, description="响应内容")
    done: bool = Field(..., description="是否完成")
    created_at: datetime = Field(..., description="创建时间")

class ModelInfo(BaseModel):
    """模型信息模型"""
    name: str = Field(..., description="模型名称")
    modified_at: datetime = Field(..., description="修改时间")
    size: int = Field(..., description="模型大小")
    digest: str = Field(..., description="模型摘要")

class TagsResponse(BaseModel):
    """模型列表响应模型"""
    models: List[ModelInfo] = Field(..., description="模型列表")

class ConfigReloadResponse(BaseModel):
    """配置重载响应模型"""
    status: str = Field(..., description="重载状态")
    message: str = Field(..., description="重载消息")
    timestamp: datetime = Field(..., description="重载时间")
    servers_loaded: int = Field(..., description="加载的服务器数量")
