"""
FastAPI主应用程序
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import logging
import time
import os

# 导入应用模块
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import db_manager
from app.config_manager import config_manager
from app.logging_manager import logging_manager
from app.load_balancer import load_balancer
from app.request_proxy import request_proxy
from app.resource_monitor_client import resource_monitor_client
from app.models import (
    HealthCheckResponse, StatusResponse, ConfigReloadResponse,
    OllamaRequest, TagsResponse, ModelInfo
)

# 设置日志
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Ollama负载均衡代理服务",
    description="智能负载均衡代理服务，为Ollama模型部署提供高可用性和性能优化",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 应用启动时间
app_start_time = time.time()

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        logger.info("正在启动Ollama负载均衡代理服务...")
        
        # 初始化数据库
        db_manager.initialize()
        logger.info("数据库初始化完成")
        
        # 负载均衡器初始化（实时数据库模式）
        logger.info("负载均衡器初始化完成（实时数据库模式）")
        
        logger.info("Ollama负载均衡代理服务启动成功")
        
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("正在关闭Ollama负载均衡代理服务...")
    
    try:
        # 关闭数据库连接
        db_manager.close()
        logger.info("数据库连接已关闭")
        
    except Exception as e:
        logger.error(f"服务关闭时发生错误: {e}")
    
    logger.info("Ollama负载均衡代理服务已关闭")

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """健康检查接口"""
    try:
        # 检查数据库连接
        with db_manager.get_db_session() as session:
            servers_count = session.execute("SELECT COUNT(*) FROM ollama_servers").scalar()
        
        return HealthCheckResponse(
            status="healthy",
            timestamp=datetime.now(),
            version="1.0.0",
            database="connected",
            servers_count=servers_count
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=503, detail=f"服务不健康: {str(e)}")

@app.get("/status", response_model=StatusResponse)
async def get_status():
    """获取系统状态"""
    try:
        uptime_seconds = time.time() - app_start_time
        uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"
        
        # 获取服务器统计
        stats = load_balancer.get_server_statistics()
        total_servers = stats['total_servers']
        active_servers = stats['enabled_servers']
        
        return StatusResponse(
            service_name="Ollama负载均衡代理服务",
            version="1.0.0",
            uptime=uptime_str,
            active_servers=active_servers,
            total_servers=total_servers,
            load_balancer_status="running"
        )
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@app.post("/config/reload", response_model=ConfigReloadResponse)
async def reload_config():
    """重载配置"""
    try:
        logger.info("收到配置重载请求")
        
        # 重载负载均衡器配置
        load_balancer.reload_config()
        
        # 获取重载后的服务器数量
        servers_loaded = len(load_balancer.get_all_virtual_models())
        
        return ConfigReloadResponse(
            status="success",
            message="配置重载成功",
            timestamp=datetime.now(),
            servers_loaded=servers_loaded
        )
    except Exception as e:
        logger.error(f"配置重载失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置重载失败: {str(e)}")

@app.post("/config/refresh-cache")
async def refresh_cache():
    """获取当前服务器状态统计"""
    try:
        logger.info("收到获取服务器状态请求")
        
        # 获取实时统计信息
        stats = load_balancer.get_server_statistics()
        
        return {
            "status": "success",
            "message": "实时数据库查询模式，无需缓存",
            "timestamp": datetime.now(),
            "total_servers": stats['total_servers'],
            "enabled_servers": stats['enabled_servers'],
            "disabled_servers": stats['disabled_servers'],
            "virtual_models": stats['virtual_models']
        }
    except Exception as e:
        logger.error(f"获取服务器统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务器统计失败: {str(e)}")

@app.get("/admin/model-usage/stats")
async def get_model_usage_stats():
    """获取模型使用统计信息"""
    try:
        usage_stats = resource_monitor_client.get_model_usage_stats()
        
        return {
            "status": "success",
            "timestamp": datetime.now(),
            "data": usage_stats
        }
    except Exception as e:
        logger.error(f"获取模型使用统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型使用统计失败: {str(e)}")

@app.post("/admin/model-usage/clear")
async def clear_model_usage_history():
    """清空模型使用历史"""
    try:
        resource_monitor_client.clear_model_usage_history()
        
        return {
            "status": "success",
            "message": "模型使用历史已清空",
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"清空模型使用历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空模型使用历史失败: {str(e)}")

@app.get("/admin/resource-monitor/config")
async def get_resource_monitor_config():
    """获取资源监控配置信息"""
    try:
        config = resource_monitor_client.get_config()
        
        return {
            "status": "success",
            "timestamp": datetime.now(),
            "data": config
        }
    except Exception as e:
        logger.error(f"获取资源监控配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资源监控配置失败: {str(e)}")

@app.get("/admin/model-type/check/{model_name}")
async def check_model_type_recommendation(model_name: str):
    """检查指定模型当前推荐使用的服务器类型"""
    try:
        # 获取该模型的所有可用服务器
        servers = load_balancer.get_servers_for_model(model_name)
        
        if not servers:
            return {
                "status": "error",
                "message": f"虚拟模型 {model_name} 没有配置的服务器",
                "timestamp": datetime.now(),
                "model_name": model_name,
                "recommendation": None
            }
        
        # 分析服务器类型分布
        server_types = {}
        healthy_servers = []
        
        for server in servers:
            server_type = server.get('type', 'CPU')
            server_url = server['server_url']
            actual_model = server['actual_model_name']
            
            # 进行健康检查
            is_healthy, health_time = await load_balancer.check_server_health(server_url, actual_model)
            
            server_info = {
                "server_url": server_url,
                "actual_model_name": actual_model,
                "type": server_type,
                "performance": server.get('performance', 0),
                "priority": server['priority'],
                "weight": server['weight'],
                "is_healthy": is_healthy,
                "health_check_time": health_time,
                "skip_resource_check": server.get('skip_resource_check', False)
            }
            
            if server_type not in server_types:
                server_types[server_type] = {
                    "count": 0,
                    "healthy_count": 0,
                    "servers": []
                }
            
            server_types[server_type]["count"] += 1
            server_types[server_type]["servers"].append(server_info)
            
            if is_healthy:
                server_types[server_type]["healthy_count"] += 1
                healthy_servers.append(server_info)
        
        # 确定推荐的服务器类型
        recommendation = None
        if healthy_servers:
            # 按优先级和权重排序找到最优服务器
            best_server = min(healthy_servers, key=lambda x: (x['priority'], -x['weight']))
            recommendation = {
                "recommended_type": best_server['type'],
                "reason": f"基于优先级({best_server['priority']})和权重({best_server['weight']})的最优选择",
                "best_server": best_server
            }
        else:
            # 如果没有健康的服务器，推荐配置最多的类型
            if server_types:
                most_common_type = max(server_types.keys(), key=lambda k: server_types[k]["count"])
                recommendation = {
                    "recommended_type": most_common_type,
                    "reason": f"没有健康服务器，推荐配置最多的类型({server_types[most_common_type]['count']}个服务器)",
                    "best_server": None
                }
        
        return {
            "status": "success",
            "timestamp": datetime.now(),
            "model_name": model_name,
            "total_servers": len(servers),
            "healthy_servers": len(healthy_servers),
            "server_types": server_types,
            "recommendation": recommendation
        }
        
    except Exception as e:
        logger.error(f"检查模型类型推荐失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查模型类型推荐失败: {str(e)}")

@app.get("/admin/model-type/overview")
async def get_model_type_overview():
    """获取所有模型的类型分布概览"""
    try:
        virtual_models = load_balancer.get_all_virtual_models()
        
        overview = {
            "total_models": len(virtual_models),
            "models": {},
            "type_summary": {
                "CPU": {"models": 0, "servers": 0},
                "GPU": {"models": 0, "servers": 0}
            }
        }
        
        for model_name in virtual_models:
            servers = load_balancer.get_servers_for_model(model_name)
            
            model_info = {
                "total_servers": len(servers),
                "types": {}
            }
            
            for server in servers:
                server_type = server.get('type', 'CPU')
                if server_type not in model_info["types"]:
                    model_info["types"][server_type] = 0
                model_info["types"][server_type] += 1
            
            # 确定主要类型
            if model_info["types"]:
                primary_type = max(model_info["types"].keys(), key=lambda k: model_info["types"][k])
                model_info["primary_type"] = primary_type
                
                # 更新类型汇总
                if primary_type in overview["type_summary"]:
                    overview["type_summary"][primary_type]["models"] += 1
                    overview["type_summary"][primary_type]["servers"] += model_info["types"][primary_type]
            else:
                model_info["primary_type"] = None
            
            overview["models"][model_name] = model_info
        
        return {
            "status": "success",
            "timestamp": datetime.now(),
            "data": overview
        }
        
    except Exception as e:
        logger.error(f"获取模型类型概览失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型类型概览失败: {str(e)}")

@app.get("/admin/server-priority/check/{model_name}")
async def check_server_priority(model_name: str):
    """检查指定模型当前会使用的服务器优先级（主要/备用）"""
    try:
        # 获取该模型的所有可用服务器
        all_servers = load_balancer.get_servers_for_model(model_name)
        
        if not all_servers:
            return {
                "status": "error",
                "message": f"虚拟模型 {model_name} 没有配置的服务器",
                "timestamp": datetime.now(),
                "model_name": model_name,
                "current_priority": None,
                "server_type": None
            }
        
        # 按优先级分组（模拟实际调用逻辑）
        priority_groups = {}
        for server in all_servers:
            priority = server['priority']
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(server)
        
        # 按优先级顺序检查（优先级数字越小越优先）
        selected_server = None
        selected_priority = None
        
        for priority in sorted(priority_groups.keys()):
            group_servers = priority_groups[priority]
            
            # 在同一优先级内，按权重排序（权重高的优先）
            weighted_servers = sorted(group_servers, key=lambda x: x['weight'], reverse=True)
            
            # 检查这个优先级的服务器是否可用
            for server in weighted_servers:
                server_url = server['server_url']
                actual_model = server['actual_model_name']
                
                # 进行健康检查
                is_healthy, health_time = await load_balancer.check_server_health(server_url, actual_model)
                
                if is_healthy:
                    # 进行资源检查（如果需要）
                    skip_resource_check = server.get('skip_resource_check', False)
                    resource_sufficient = True
                    
                    if not skip_resource_check and 'type' in server and 'performance' in server:
                        server_type = server['type']
                        performance = server['performance']
                        
                        is_sufficient, resource_info = await resource_monitor_client.check_server_resource(
                            server_url, server_type, performance, model_name
                        )
                        resource_sufficient = is_sufficient or resource_info.get('skipped', False)
                    
                    if resource_sufficient:
                        selected_server = server
                        selected_priority = priority
                        break
            
            # 如果在当前优先级找到可用服务器，就不再检查下一优先级
            if selected_server:
                break
        
        # 分析结果
        if selected_server:
            server_type_desc = "主要服务器" if selected_priority == 1 else "备用服务器" if selected_priority == 2 else f"优先级{selected_priority}服务器"
            task_recommendation = "复杂任务" if selected_priority == 1 else "简单任务"
            
            return {
                "status": "success",
                "timestamp": datetime.now(),
                "model_name": model_name,
                "current_priority": selected_priority,
                "server_type": server_type_desc,
                "task_recommendation": task_recommendation,
                "selected_server": {
                    "server_url": selected_server['server_url'],
                    "actual_model_name": selected_server['actual_model_name'],
                    "type": selected_server.get('type', 'CPU'),
                    "performance": selected_server.get('performance', 0),
                    "priority": selected_server['priority'],
                    "weight": selected_server['weight'],
                    "skip_resource_check": selected_server.get('skip_resource_check', False)
                },
                "priority_analysis": {
                    "total_priorities": len(priority_groups),
                    "available_priorities": list(sorted(priority_groups.keys())),
                    "servers_per_priority": {str(p): len(servers) for p, servers in priority_groups.items()}
                }
            }
        else:
            return {
                "status": "warning",
                "message": f"模型 {model_name} 的所有服务器都不可用",
                "timestamp": datetime.now(),
                "model_name": model_name,
                "current_priority": None,
                "server_type": "无可用服务器",
                "task_recommendation": "暂时无法执行任务",
                "selected_server": None,
                "priority_analysis": {
                    "total_priorities": len(priority_groups),
                    "available_priorities": list(sorted(priority_groups.keys())),
                    "servers_per_priority": {str(p): len(servers) for p, servers in priority_groups.items()}
                }
            }
        
    except Exception as e:
        logger.error(f"检查服务器优先级失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查服务器优先级失败: {str(e)}")

@app.get("/admin/server-priority/overview")
async def get_server_priority_overview():
    """获取所有模型的服务器优先级分布概览"""
    try:
        virtual_models = load_balancer.get_all_virtual_models()
        
        overview = {
            "total_models": len(virtual_models),
            "priority_summary": {
                "1": {"models": 0, "description": "主要服务器（复杂任务）"},
                "2": {"models": 0, "description": "备用服务器（简单任务）"},
                "other": {"models": 0, "description": "其他优先级"}
            },
            "models": {}
        }
        
        for model_name in virtual_models:
            servers = load_balancer.get_servers_for_model(model_name)
            
            # 分析每个模型的优先级分布
            priority_dist = {}
            for server in servers:
                priority = server['priority']
                if priority not in priority_dist:
                    priority_dist[priority] = 0
                priority_dist[priority] += 1
            
            # 确定当前会使用的优先级（最小的优先级数字）
            current_priority = min(priority_dist.keys()) if priority_dist else None
            
            model_info = {
                "total_servers": len(servers),
                "priority_distribution": priority_dist,
                "current_priority": current_priority,
                "server_type": "主要服务器" if current_priority == 1 else "备用服务器" if current_priority == 2 else f"优先级{current_priority}服务器" if current_priority else "无服务器",
                "task_recommendation": "复杂任务" if current_priority == 1 else "简单任务" if current_priority == 2 else "其他" if current_priority else "无法执行"
            }
            
            overview["models"][model_name] = model_info
            
            # 更新汇总统计
            if current_priority == 1:
                overview["priority_summary"]["1"]["models"] += 1
            elif current_priority == 2:
                overview["priority_summary"]["2"]["models"] += 1
            elif current_priority is not None:
                overview["priority_summary"]["other"]["models"] += 1
        
        return {
            "status": "success",
            "timestamp": datetime.now(),
            "data": overview
        }
        
    except Exception as e:
        logger.error(f"获取服务器优先级概览失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务器优先级概览失败: {str(e)}")

@app.get("/api/tags", response_model=TagsResponse)
async def get_tags():
    """获取可用模型列表"""
    try:
        virtual_models = load_balancer.get_all_virtual_models()
        
        models = []
        for model_name in virtual_models:
            models.append(ModelInfo(
                name=model_name,
                modified_at=datetime.now(),
                size=0,  # 虚拟模型大小设为0
                digest="virtual-model"
            ))
        
        return TagsResponse(models=models)
        
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@app.get("/v1/models")
async def get_v1_models():
    """OpenAI API兼容的模型列表接口"""
    try:
        virtual_models = load_balancer.get_all_virtual_models()
        
        models = []
        for model_name in virtual_models:
            models.append({
                "id": model_name,
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "ollama-load-balancer"
            })
        
        return {
            "object": "list",
            "data": models
        }
        
    except Exception as e:
        logger.error(f"获取OpenAI兼容模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@app.post("/api/chat")
async def chat(request: Request):
    """对话生成接口"""
    try:
        json_data = await request.json()
        model_name = json_data.get('model')
        
        if not model_name:
            raise HTTPException(status_code=400, detail="缺少模型名称")
        
        # 检查是否为流式请求
        if json_data.get('stream', False):
            return await request_proxy.proxy_streaming_request(
                "POST", "/api/chat", model_name,
                headers=dict(request.headers),
                json_data=json_data
            )
        else:
            return await request_proxy.proxy_request(
                "POST", "/api/chat", model_name,
                headers=dict(request.headers),
                json_data=json_data
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对话生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话生成失败: {str(e)}")

@app.post("/api/generate")
async def generate(request: Request):
    """文本生成接口"""
    try:
        json_data = await request.json()
        model_name = json_data.get('model')
        
        if not model_name:
            raise HTTPException(status_code=400, detail="缺少模型名称")
        
        # 检查是否为流式请求
        if json_data.get('stream', False):
            return await request_proxy.proxy_streaming_request(
                "POST", "/api/generate", model_name,
                headers=dict(request.headers),
                json_data=json_data
            )
        else:
            return await request_proxy.proxy_request(
                "POST", "/api/generate", model_name,
                headers=dict(request.headers),
                json_data=json_data
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文本生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"文本生成失败: {str(e)}")

@app.post("/api/embeddings")
async def embeddings(request: Request):
    """嵌入向量生成接口"""
    try:
        json_data = await request.json()
        model_name = json_data.get('model')
        
        if not model_name:
            raise HTTPException(status_code=400, detail="缺少模型名称")
        
        return await request_proxy.proxy_request(
            "POST", "/api/embeddings", model_name,
            headers=dict(request.headers),
            json_data=json_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"嵌入向量生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"嵌入向量生成失败: {str(e)}")

@app.post("/api/show")
async def show_model(request: Request):
    """获取模型信息接口"""
    try:
        json_data = await request.json()
        model_name = json_data.get('name') or json_data.get('model')
        
        if not model_name:
            raise HTTPException(status_code=400, detail="缺少模型名称")
        
        return await request_proxy.proxy_request(
            "POST", "/api/show", model_name,
            headers=dict(request.headers),
            json_data=json_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型信息失败: {str(e)}")

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI API兼容的对话完成接口"""
    try:
        json_data = await request.json()
        model_name = json_data.get('model')
        
        if not model_name:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": "Missing required parameter: model",
                        "type": "invalid_request_error",
                        "param": "model",
                        "code": None
                    }
                }
            )
        
        # 转换OpenAI格式到Ollama格式
        messages = json_data.get('messages', [])
        stream = json_data.get('stream', False)
        
        # 构建Ollama chat请求
        ollama_request = {
            'model': model_name,
            'messages': messages,
            'stream': stream
        }
        
        # 传递其他参数
        if 'temperature' in json_data:
            ollama_request.setdefault('options', {})['temperature'] = json_data['temperature']
        if 'max_tokens' in json_data:
            ollama_request.setdefault('options', {})['num_predict'] = json_data['max_tokens']
        if 'top_p' in json_data:
            ollama_request.setdefault('options', {})['top_p'] = json_data['top_p']
        
        if stream:
            # 流式响应 - 需要特殊处理OpenAI格式
            async def openai_stream_generator():
                try:
                    # 获取Ollama流式响应
                    streaming_response = await request_proxy.proxy_streaming_request(
                        "POST", "/api/chat", model_name,
                        headers=dict(request.headers),
                        json_data=ollama_request
                    )
                    
                    # 转换为OpenAI流式格式
                    async for chunk in streaming_response.body_iterator:
                        if chunk.strip():
                            try:
                                import json
                                ollama_data = json.loads(chunk)
                                
                                # 转换为OpenAI格式
                                openai_chunk = {
                                    "id": f"chatcmpl-{int(datetime.now().timestamp())}",
                                    "object": "chat.completion.chunk",
                                    "created": int(datetime.now().timestamp()),
                                    "model": model_name,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": ollama_data.get('message', {}).get('content', '')
                                        },
                                        "finish_reason": "stop" if ollama_data.get('done', False) else None
                                    }]
                                }
                                
                                yield f"data: {json.dumps(openai_chunk)}\n\n"
                                
                                if ollama_data.get('done', False):
                                    yield "data: [DONE]\n\n"
                                    break
                                    
                            except json.JSONDecodeError:
                                continue
                                
                except Exception as e:
                    logger.error(f"流式响应处理失败: {e}")
                    error_chunk = {
                        "error": {
                            "message": str(e),
                            "type": "server_error"
                        }
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
            
            return StreamingResponse(
                openai_stream_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        else:
            # 非流式响应
            try:
                ollama_response = await request_proxy.proxy_request(
                    "POST", "/api/chat", model_name,
                    headers=dict(request.headers),
                    json_data=ollama_request
                )
                
                # 检查Ollama响应格式
                if isinstance(ollama_response, dict) and 'error' in ollama_response:
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": {
                                "message": ollama_response.get('error', 'Unknown error'),
                                "type": "server_error",
                                "code": None
                            }
                        }
                    )
                
                # 转换Ollama响应到OpenAI格式
                content = ""
                if isinstance(ollama_response, dict):
                    message = ollama_response.get('message', {})
                    if isinstance(message, dict):
                        content = message.get('content', '')
                    elif isinstance(message, str):
                        content = message
                    else:
                        content = str(ollama_response.get('response', ''))
                else:
                    content = str(ollama_response)
                
                openai_response = {
                    "id": f"chatcmpl-{int(datetime.now().timestamp())}",
                    "object": "chat.completion",
                    "created": int(datetime.now().timestamp()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                }
                
                return JSONResponse(content=openai_response)
                
            except Exception as proxy_error:
                logger.error(f"代理请求失败: {proxy_error}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "message": f"Proxy request failed: {str(proxy_error)}",
                            "type": "server_error",
                            "code": None
                        }
                    }
                )
            
    except Exception as e:
        logger.error(f"OpenAI兼容对话完成失败: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": f"Internal server error: {str(e)}",
                    "type": "server_error",
                    "code": None
                }
            }
        )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务器错误"}
    )

if __name__ == "__main__":
    # 从配置获取服务器参数
    host = config_manager.get('server.host', '0.0.0.0')
    port = config_manager.get('server.port', 8083)
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
