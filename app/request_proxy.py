"""
请求代理模块
"""

import httpx
import asyncio
import uuid
import time
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
try:
    from .load_balancer import load_balancer
    from .logging_manager import logging_manager
    from .resource_monitor_client import resource_monitor_client
except ImportError:
    from app.load_balancer import load_balancer
    from app.logging_manager import logging_manager
    from app.resource_monitor_client import resource_monitor_client
import logging
import json

logger = logging.getLogger(__name__)

class RequestProxy:
    """请求代理器"""
    
    def __init__(self):
        self.client_timeout = 300.0  # 5分钟超时
    
    async def proxy_request(self, method: str, path: str, 
                          model_name: str = None, 
                          headers: Dict[str, str] = None,
                          json_data: Dict[str, Any] = None,
                          params: Dict[str, str] = None) -> Dict[str, Any]:
        """代理请求到后端服务器"""
        
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # 如果是模型相关的请求，需要进行负载均衡
            if model_name and path.startswith('/api/'):
                return await self._proxy_model_request(
                    request_id, method, path, model_name, 
                    headers, json_data, params, start_time
                )
            else:
                # 非模型请求，返回错误
                raise HTTPException(status_code=404, detail="Endpoint not found")
                
        except HTTPException:
            raise
        except Exception as e:
            logging_manager.log_error(e, request_id=request_id)
            raise HTTPException(status_code=500, detail=f"代理请求失败: {str(e)}")
    
    async def _proxy_model_request(self, request_id: str, method: str, path: str,
                                 model_name: str, headers: Dict[str, str],
                                 json_data: Dict[str, Any], params: Dict[str, str],
                                 start_time: float) -> Dict[str, Any]:
        """代理模型相关请求 - 智能回退策略"""
        
        # 获取所有可用服务器（按优先级排序）
        all_servers = load_balancer.get_servers_for_model(model_name)
        if not all_servers:
            raise HTTPException(
                status_code=503, 
                detail=f"虚拟模型 {model_name} 没有配置的服务器"
            )
        
        # 按优先级分组并在组内应用权重逻辑
        priority_groups = {}
        for server in all_servers:
            priority = server['priority']
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(server)
        
        # 按优先级顺序尝试，在每个优先级内按权重排序尝试
        last_error = None
        total_attempts = 0
        total_servers = sum(len(servers) for servers in priority_groups.values())
        
        logger.info(f"[{request_id}] 开始轮询所有服务器: 模型 {model_name}, 共 {total_servers} 个服务器, {len(priority_groups)} 个优先级")
        
        for priority in sorted(priority_groups.keys()):
            group_servers = priority_groups[priority]
            
            # 在同一优先级内，按权重排序（权重高的优先尝试）
            # 但仍然会尝试该优先级的所有服务器
            weighted_servers = self._get_weighted_server_order(group_servers)
            
            logger.info(f"[{request_id}] 开始尝试优先级 {priority} 的 {len(weighted_servers)} 个服务器")
            
            for server in weighted_servers:
                total_attempts += 1
                try:
                    logger.info(f"[{request_id}] 尝试服务器 {total_attempts}/{total_servers}: {server['server_url']} (优先级: {priority}, 权重: {server['weight']})")
                    return await self._try_single_server(
                        request_id, method, path, model_name, server,
                        headers, json_data, params, start_time, total_attempts
                    )
                except Exception as e:
                    last_error = e
                    logger.warning(f"[{request_id}] 服务器请求失败 {total_attempts}/{total_servers}: {model_name} -> {server['actual_model_name']} (服务器: {server['server_url']}, 优先级: {priority}, 权重: {server['weight']}, 错误: {str(e)})")
                    continue
            
            logger.warning(f"[{request_id}] 优先级 {priority} 的所有 {len(weighted_servers)} 个服务器都失败，尝试下一优先级")
        
        # 所有服务器都失败了 - 完整轮询结束
        logger.error(f"[{request_id}] 轮询结束: 模型 {model_name} 的所有 {total_servers} 个服务器都不可用，最后错误: {str(last_error)}")
        raise HTTPException(
            status_code=503,
            detail=f"虚拟模型 {model_name} 的所有 {total_servers} 个服务器都不可用，已完成完整轮询: {str(last_error)}"
        )
        
    
    async def _try_single_server(self, request_id: str, method: str, path: str,
                               model_name: str, server: Dict[str, Any],
                               headers: Dict[str, str], json_data: Dict[str, Any],
                               params: Dict[str, str], start_time: float, attempt: int) -> Dict[str, Any]:
        """尝试单个服务器"""
        
        server_url = server['server_url']
        actual_model_name = server['actual_model_name']
        
        # 复制json_data以避免修改原始数据
        request_json = json_data.copy() if json_data else None
        if request_json and 'model' in request_json:
            request_json['model'] = actual_model_name
        
        # 记录请求开始
        logger.info(f"[{request_id}] 开始请求虚拟模型 '{model_name}' -> 实际模型 '{actual_model_name}' (服务器: {server_url}, 尝试: {attempt})")
        logging_manager.log_request(
            request_id, method, f"{server_url}{path}",
            model_name=model_name, server_url=server_url,
            message=f"尝试服务器 {attempt} - 开始请求"
        )
        
        # 先进行快速健康检查
        is_healthy, health_time = await load_balancer.check_server_health(server_url, actual_model_name)
        if not is_healthy:
            raise Exception(f"服务器健康检查失败: {server_url}")
        
        # 进行资源充足性检查
        # 检查是否配置跳过资源检测
        skip_resource_check = server.get('skip_resource_check', False)
        
        if skip_resource_check:
            logger.info(f"[{request_id}] ⏭️ 配置跳过资源检查: {server_url} 模型 {model_name} (skip_resource_check=True)")
        else:
            # 检查必需字段
            if 'type' not in server or 'performance' not in server:
                raise Exception(f"服务器配置缺少必需字段: {server_url}")
            
            server_type = server['type']
            performance = server['performance']
            
            logger.info(f"[{request_id}] 📊 资源检查开始: 服务器 {server_url} (类型: {server_type}, 模型需求: {performance}GB)")
            
            is_sufficient, resource_info = await resource_monitor_client.check_server_resource(
                server_url, server_type, performance, model_name
            )
            
            # 详细的资源信息日志
            available_gb = resource_info.get('available_gb', 0)
            total_gb = resource_info.get('total_gb', 0)
            usage_percent = resource_info.get('usage_percent', 0)
            
            if resource_info.get('skipped', False):
                logger.info(f"[{request_id}] ⏭️ 跳过资源检查: {server_url} 模型 {model_name} 可能正在使用中 (5分钟内已调用)")
            else:
                logger.info(f"[{request_id}] 📈 资源状态: {server_url} | 类型: {server_type} | 总容量: {total_gb:.1f}GB | 可用: {available_gb:.1f}GB | 使用率: {usage_percent:.1f}% | 需求: {performance}GB")
            
            if not is_sufficient and not resource_info.get('skipped', False):
                error_msg = f"服务器资源不足: {server_url} (类型: {server_type}, 需求: {performance}GB, 可用: {available_gb:.1f}GB/{total_gb:.1f}GB, 使用率: {usage_percent:.1f}%)"
                logger.warning(f"[{request_id}] ❌ {error_msg}")
                raise Exception(error_msg)
            elif is_sufficient:
                logger.info(f"[{request_id}] ✅ 资源充足: {server_url} 满足 {model_name} 需求 ({performance}GB), 选择此服务器")
        
        try:
            async with httpx.AsyncClient(timeout=self.client_timeout) as client:
                # 清理和准备headers
                clean_headers = {}
                if headers:
                    for key, value in headers.items():
                        if key.lower() not in ['content-length', 'transfer-encoding', 'connection']:
                            clean_headers[key] = value
                
                # 构建请求
                request_kwargs = {
                    'method': method,
                    'url': f"{server_url}{path}",
                    'headers': clean_headers,
                    'params': params or {}
                }
                
                if request_json:
                    request_kwargs['json'] = request_json
                
                # 发送请求
                response = await client.request(**request_kwargs)
                response_time = time.time() - start_time
                
                # 记录响应
                logger.info(f"[{request_id}] 请求成功: {model_name} -> {actual_model_name} (服务器: {server_url}, 状态: {response.status_code}, 耗时: {response_time:.3f}s)")
                logging_manager.log_request(
                    request_id, method, f"{server_url}{path}",
                    model_name=model_name, server_url=server_url,
                    response_time=response_time, status_code=response.status_code,
                    message=f"尝试服务器 {attempt} - 请求完成"
                )
                
                # 检查HTTP状态码
                if response.status_code == 404:
                    raise Exception(f"模型或接口不存在: {response.status_code}")
                elif response.status_code == 503:
                    raise Exception(f"服务不可用: {response.status_code}")
                elif response.status_code >= 500:
                    raise Exception(f"服务器内部错误: {response.status_code}")
                elif response.status_code >= 400:
                    # 4xx错误也需要重试其他服务器，因为不同服务器可能有不同的模型
                    logger.warning(f"[{request_id}] 服务器返回4xx错误，将尝试下一个服务器: {server_url} (状态码: {response.status_code})")
                    raise Exception(f"客户端错误 {response.status_code}: {response.text}")
                
                # 记录性能
                logging_manager.log_performance(
                    f"{method} {path}", response_time,
                    server_url=server_url, model_name=model_name,
                    request_id=request_id
                )
                
                # 处理响应数据
                try:
                    response_data = response.json()
                    
                    # 将实际模型名替换回虚拟模型名
                    if isinstance(response_data, dict):
                        if 'model' in response_data:
                            response_data['model'] = model_name
                        elif 'models' in response_data:
                            # 处理 /api/tags 响应
                            for model_info in response_data['models']:
                                if model_info.get('name') == actual_model_name:
                                    model_info['name'] = model_name
                    
                    # 请求成功，增加服务器计数
                    from .database import db_manager
                    db_manager.increment_server_count(server['id'])
                    
                    logger.info(f"请求成功: {server_url} -> {actual_model_name} (尝试 {attempt})")
                    return response_data
                    
                except json.JSONDecodeError:
                    # 如果不是JSON响应，直接返回文本
                    return {"response": response.text}
                
        except httpx.TimeoutException:
            error_msg = f"请求超时: {server_url}{path}"
            logging_manager.log_error(
                Exception(error_msg), request_id=request_id,
                server_url=server_url, model_name=model_name
            )
            raise Exception(error_msg)
            
        except httpx.RequestError as e:
            error_msg = f"连接错误: {str(e)}"
            logging_manager.log_error(
                e, request_id=request_id,
                server_url=server_url, model_name=model_name
            )
            raise Exception(error_msg)
        
        except HTTPException:
            # HTTPException需要直接抛出，不进行重试
            raise
        
        except Exception as e:
            # 其他异常记录日志后重新抛出
            logging_manager.log_error(
                e, request_id=request_id,
                server_url=server_url, model_name=model_name
            )
            raise
    
    def _get_weighted_server_order(self, servers: List[Dict]) -> List[Dict]:
        """获取按权重排序的服务器列表（权重高的优先，但会尝试所有服务器）"""
        if not servers:
            return []
        
        if len(servers) == 1:
            return servers
        
        # 按权重降序排序，权重相同时保持原顺序
        return sorted(servers, key=lambda x: x['weight'], reverse=True)
    
    async def proxy_streaming_request(self, method: str, path: str,
                                    model_name: str, headers: Dict[str, str] = None,
                                    json_data: Dict[str, Any] = None) -> StreamingResponse:
        """代理流式请求 - 智能回退策略"""
        
        request_id = str(uuid.uuid4())
        
        # 获取所有可用服务器
        all_servers = load_balancer.get_servers_for_model(model_name)
        if not all_servers:
            raise HTTPException(
                status_code=503,
                detail=f"虚拟模型 {model_name} 没有配置的服务器"
            )
        
        # 按优先级分组并在组内应用权重逻辑
        priority_groups = {}
        for server in all_servers:
            priority = server['priority']
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(server)
        
        # 按优先级顺序尝试，在每个优先级内按权重排序尝试
        total_attempts = 0
        last_error = None
        total_servers = sum(len(servers) for servers in priority_groups.values())
        
        logger.info(f"[{request_id}] 开始轮询所有服务器进行流式请求: 模型 {model_name}, 共 {total_servers} 个服务器, {len(priority_groups)} 个优先级")
        
        for priority in sorted(priority_groups.keys()):
            group_servers = priority_groups[priority]
            weighted_servers = self._get_weighted_server_order(group_servers)
            
            logger.info(f"[{request_id}] 开始尝试优先级 {priority} 的 {len(weighted_servers)} 个服务器（流式请求）")
            
            for server in weighted_servers:
                total_attempts += 1
                try:
                    # 先进行健康检查
                    is_healthy, _ = await load_balancer.check_server_health(
                        server['server_url'], server['actual_model_name']
                    )
                    if not is_healthy:
                        logger.warning(f"[{request_id}] 流式请求跳过不健康的服务器 {total_attempts}/{total_servers}: {model_name} -> {server['actual_model_name']} (服务器: {server['server_url']}, 优先级: {priority})")
                        last_error = Exception(f"服务器健康检查失败: {server['server_url']}")
                        continue
                    
                    # 进行资源充足性检查
                    # 检查是否配置跳过资源检测
                    skip_resource_check = server.get('skip_resource_check', False)
                    
                    if skip_resource_check:
                        logger.info(f"[{request_id}] ⏭️ 流式请求配置跳过资源检查: {server['server_url']} 模型 {model_name} (skip_resource_check=True)")
                    else:
                        server_type = server.get('type', 'CPU')
                        performance = server.get('performance', 8)
                        
                        logger.info(f"[{request_id}] 📊 流式请求资源检查: 服务器 {server['server_url']} (类型: {server_type}, 模型需求: {performance}GB)")
                        
                        is_sufficient, resource_info = await resource_monitor_client.check_server_resource(
                            server['server_url'], server_type, performance, model_name
                        )
                        
                        # 详细的资源信息日志
                        available_gb = resource_info.get('available_gb', 0)
                        total_gb = resource_info.get('total_gb', 0)
                        usage_percent = resource_info.get('usage_percent', 0)
                        
                        if resource_info.get('skipped', False):
                            logger.info(f"[{request_id}] ⏭️ 流式请求跳过资源检查: {server['server_url']} 模型 {model_name} 可能正在使用中 (5分钟内已调用)")
                        else:
                            logger.info(f"[{request_id}] 📈 流式请求资源状态: {server['server_url']} | 类型: {server_type} | 总容量: {total_gb:.1f}GB | 可用: {available_gb:.1f}GB | 使用率: {usage_percent:.1f}% | 需求: {performance}GB")
                        
                        if not is_sufficient and not resource_info.get('skipped', False):
                            error_msg = f"服务器资源不足: {server['server_url']} (类型: {server_type}, 需求: {performance}GB, 可用: {available_gb:.1f}GB/{total_gb:.1f}GB, 使用率: {usage_percent:.1f}%)"
                            logger.warning(f"[{request_id}] ❌ 流式请求跳过资源不足的服务器 {total_attempts}/{total_servers}: {error_msg}")
                            last_error = Exception(error_msg)
                            continue
                        elif is_sufficient:
                            logger.info(f"[{request_id}] ✅ 流式请求资源充足: {server['server_url']} 满足 {model_name} 需求 ({performance}GB), 选择此服务器")
                    
                    # 使用这个服务器进行流式传输
                    logger.info(f"[{request_id}] 尝试流式传输 {total_attempts}/{total_servers}: {model_name} -> {server['actual_model_name']} (服务器: {server['server_url']}, 优先级: {priority}, 权重: {server['weight']})")
                    return await self._create_streaming_response(
                        request_id, method, path, model_name, server, headers, json_data, total_attempts
                    )
                    
                except Exception as e:
                    last_error = e
                    logger.warning(f"[{request_id}] 流式请求服务器失败 {total_attempts}/{total_servers}: {model_name} -> {server['actual_model_name']} (服务器: {server['server_url']}, 优先级: {priority}, 权重: {server['weight']}, 错误: {str(e)})")
                    continue
            
            logger.warning(f"[{request_id}] 优先级 {priority} 的所有 {len(weighted_servers)} 个服务器都失败，尝试下一优先级")
        
        # 所有服务器都失败 - 完整轮询结束
        logger.error(f"[{request_id}] 流式请求轮询结束: 模型 {model_name} 的所有 {total_servers} 个服务器都不可用，最后错误: {str(last_error)}")
        raise HTTPException(
            status_code=503,
            detail=f"虚拟模型 {model_name} 的所有 {total_servers} 个服务器都不可用于流式请求，已完成完整轮询: {str(last_error)}"
        )
    
    async def _create_streaming_response(self, request_id: str, method: str, path: str,
                                       model_name: str, server: Dict[str, Any],
                                       headers: Dict[str, str], json_data: Dict[str, Any],
                                       attempt: int) -> StreamingResponse:
        """创建流式响应"""
        
        server_url = server['server_url']
        actual_model_name = server['actual_model_name']
        
        # 复制json_data以避免修改原始数据
        request_json = json_data.copy() if json_data else None
        if request_json and 'model' in request_json:
            request_json['model'] = actual_model_name
        
        async def stream_generator():
            try:
                logger.info(f"[{request_id}] 开始代理请求: {method} {path} (模型: {model_name}) (尝试 {attempt})")
                
                async with httpx.AsyncClient(timeout=self.client_timeout) as client:
                    # 清理headers
                    clean_headers = {}
                    if headers:
                        for key, value in headers.items():
                            if key.lower() not in ['content-length', 'transfer-encoding', 'connection']:
                                clean_headers[key] = value
                    
                    async with client.stream(
                        method, f"{server_url}{path}",
                        headers=clean_headers,
                        json=request_json
                    ) as response:
                        
                        if response.status_code == 404:
                            error_msg = f"模型或接口不存在: {response.status_code}"
                            logger.warning(f"[{request_id}] 服务器返回404，将尝试下一个服务器: {server_url}")
                            raise Exception(error_msg)
                        elif response.status_code >= 500:
                            error_msg = f"服务器错误: {response.status_code}"
                            logger.warning(f"[{request_id}] 服务器返回5xx错误，将尝试下一个服务器: {server_url}")
                            raise Exception(error_msg)
                        elif response.status_code >= 400:
                            error_text = await response.aread()
                            error_msg = f"客户端错误 {response.status_code}: {error_text.decode()}"
                            logger.warning(f"[{request_id}] 服务器返回4xx错误，将尝试下一个服务器: {server_url}")
                            raise Exception(error_msg)
                        
                        # 请求成功，增加服务器计数
                        from .database import db_manager
                        db_manager.increment_server_count(server['id'])
                        
                        logger.info(f"流式请求成功建立: {server_url} -> {actual_model_name}")
                        
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                try:
                                    # 尝试解析JSON并替换模型名
                                    data = json.loads(chunk)
                                    if isinstance(data, dict) and 'model' in data:
                                        data['model'] = model_name
                                    yield json.dumps(data, ensure_ascii=False) + '\n'
                                except json.JSONDecodeError:
                                    # 如果不是JSON，直接返回
                                    yield chunk
                                    
            except Exception as e:
                error_msg = f"流式请求异常: {str(e)}"
                logger.error(error_msg)
                logging_manager.log_error(
                    e, request_id=request_id,
                    server_url=server_url, model_name=model_name
                )
                yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

# 全局请求代理实例
request_proxy = RequestProxy()
