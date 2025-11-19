"""
负载均衡器
"""

import random
import asyncio
import httpx
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
try:
    from .database import db_manager, OllamaServer
    from .config_manager import config_manager
    from .logging_manager import logging_manager
except ImportError:
    # 绝对导入作为备选
    from app.database import db_manager, OllamaServer
    from app.config_manager import config_manager
    from app.logging_manager import logging_manager
import logging
import time

logger = logging.getLogger(__name__)

class LoadBalancer:
    """负载均衡器 - 实时数据库查询版本"""
    
    def __init__(self):
        self.health_check_timeout = config_manager.get('load_balancer.health_check_timeout', 3.0)
        self.max_retries = config_manager.get('load_balancer.max_retries', 3)
    
    def _get_servers_from_db(self, virtual_model_name: str = None) -> Dict[str, List[Dict]]:
        """实时从数据库获取服务器配置"""
        try:
            logger.info(f"查询数据库获取服务器配置 (虚拟模型: {virtual_model_name})")
            with db_manager.get_db_session() as session:
                # 构建查询
                query = session.query(OllamaServer).filter(OllamaServer.is_active == True)
                if virtual_model_name:
                    query = query.filter(OllamaServer.virtual_model_name == virtual_model_name)
                
                servers = query.all()
                logger.info(f"数据库查询结果: 找到 {len(servers)} 个启用的服务器")
                
                # 详细记录查询到的服务器
                for server in servers:
                    logger.info(f"  - ID:{server.id} {server.virtual_model_name} -> {server.actual_model_name} ({server.server_url}) [is_active:{server.is_active}, 优先级:{server.priority}, 权重:{server.weight}, 类型:{server.type}, 性能:{server.performance}GB, 跳过资源检查:{server.skip_resource_check}]")
                
                config = {}
                for server in servers:
                    virtual_model = server.virtual_model_name
                    if virtual_model not in config:
                        config[virtual_model] = []
                    
                    config[virtual_model].append({
                        'id': server.id,
                        'server_url': server.server_url,
                        'actual_model_name': server.actual_model_name,
                        'weight': server.weight,
                        'priority': server.priority,
                        'type': server.type,
                        'performance': server.performance,
                        'skip_resource_check': server.skip_resource_check,
                        'description': server.description
                    })
                
                # 按优先级排序
                for virtual_model in config:
                    config[virtual_model].sort(key=lambda x: x['priority'])
                
                logger.info(f"最终配置: {config}")
                return config
                
        except Exception as e:
            logger.error(f"从数据库获取服务器配置失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return {}
    
    
    
    
    def get_servers_for_model(self, virtual_model_name: str) -> List[Dict]:
        """实时获取指定虚拟模型的服务器列表"""
        config = self._get_servers_from_db(virtual_model_name)
        return config.get(virtual_model_name, [])
    
    async def check_server_health(self, server_url: str, model_name: str) -> Tuple[bool, float]:
        """检查服务器健康状态 - 简化版本，减少延迟"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.health_check_timeout) as client:
                # 简化健康检查：只检查服务器是否响应，不验证模型列表
                response = await client.get(f"{server_url}/api/tags")
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    # 假设服务器响应正常就认为模型可用，避免解析JSON的开销
                    logging_manager.log_health_check(server_url, 'healthy', response_time)
                    return True, response_time
                else:
                    logging_manager.log_health_check(
                        server_url, 'unhealthy', response_time, 
                        f"HTTP {response.status_code}"
                    )
                    return False, response_time
                    
        except Exception as e:
            response_time = time.time() - start_time
            logging_manager.log_health_check(server_url, 'unhealthy', response_time, str(e))
            return False, response_time
    
    async def select_server(self, virtual_model_name: str) -> Optional[Dict]:
        """选择可用的服务器 - 实时数据库查询"""
        servers = self.get_servers_for_model(virtual_model_name)
        
        if not servers:
            logger.warning(f"未找到虚拟模型 {virtual_model_name} 的启用服务器配置")
            return None
        
        # 按优先级分组
        priority_groups = {}
        for server in servers:
            priority = server['priority']
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(server)
        
        # 按优先级顺序尝试
        for priority in sorted(priority_groups.keys()):
            group_servers = priority_groups[priority]
            
            # 优化：如果只有一个服务器，直接检查它
            if len(group_servers) == 1:
                server = group_servers[0]
                try:
                    is_healthy, response_time = await self.check_server_health(
                        server['server_url'], server['actual_model_name']
                    )
                    if is_healthy:
                        server['response_time'] = response_time
                        # 增加服务器访问计数
                        db_manager.increment_server_count(server['id'])
                        logger.info(f"为虚拟模型 '{virtual_model_name}' 选择服务器: {server['server_url']} -> 实际模型: {server['actual_model_name']} (权重: {server['weight']}, 优先级: {server['priority']})")
                        return server
                except Exception as e:
                    logger.error(f"健康检查失败 {server['server_url']}: {e}")
            else:
                # 并发检查这一优先级的所有服务器健康状态
                health_tasks = []
                for server in group_servers:
                    task = self.check_server_health(server['server_url'], server['actual_model_name'])
                    health_tasks.append((server, task))
                
                # 等待所有健康检查完成
                healthy_servers = []
                for server, task in health_tasks:
                    try:
                        is_healthy, response_time = await task
                        if is_healthy:
                            server['response_time'] = response_time
                            healthy_servers.append(server)
                    except Exception as e:
                        logger.error(f"健康检查失败 {server['server_url']}: {e}")
                
                # 如果有健康的服务器，使用加权随机选择
                if healthy_servers:
                    selected = self._weighted_random_select(healthy_servers)
                    if selected:
                        # 增加服务器访问计数
                        db_manager.increment_server_count(selected['id'])
                        logger.info(f"为虚拟模型 '{virtual_model_name}' 选择服务器: {selected['server_url']} -> 实际模型: {selected['actual_model_name']} (权重: {selected['weight']}, 优先级: {selected['priority']})")
                    return selected
            
            logger.warning(f"优先级 {priority} 的所有服务器都不可用")
        
        logger.error(f"虚拟模型 {virtual_model_name} 的所有服务器都不可用")
        return None
    
    def _weighted_random_select(self, servers: List[Dict]) -> Dict:
        """加权随机选择服务器"""
        if not servers:
            return None
        
        if len(servers) == 1:
            return servers[0]
        
        # 计算总权重
        total_weight = sum(server['weight'] for server in servers)
        
        if total_weight <= 0:
            # 如果权重都是0或负数，随机选择
            return random.choice(servers)
        
        # 加权随机选择
        random_value = random.uniform(0, total_weight)
        current_weight = 0
        
        for server in servers:
            current_weight += server['weight']
            if random_value <= current_weight:
                return server
        
        # 理论上不应该到达这里，但作为备选
        return servers[-1]
    
    def get_all_virtual_models(self) -> List[str]:
        """实时获取所有虚拟模型名称"""
        config = self._get_servers_from_db()
        return list(config.keys())
    
    def get_server_statistics(self) -> Dict[str, int]:
        """获取服务器统计信息"""
        try:
            logger.info("开始查询数据库获取服务器统计信息...")
            with db_manager.get_db_session() as session:
                logger.info("数据库会话已建立，开始查询所有服务器...")
                all_servers = session.query(OllamaServer).all()
                logger.info(f"数据库查询完成，共找到 {len(all_servers)} 个服务器记录")
                
                if not all_servers:
                    logger.warning("数据库中没有找到任何服务器记录！")
                    return {'total_servers': 0, 'enabled_servers': 0, 'disabled_servers': 0, 'virtual_models': 0}
                
                enabled_servers = [s for s in all_servers if s.is_active]
                disabled_servers = [s for s in all_servers if not s.is_active]
                
                logger.info(f"服务器分类统计: 启用={len(enabled_servers)}, 禁用={len(disabled_servers)}")
                
                # 记录启用的服务器
                if enabled_servers:
                    logger.info("当前启用的服务器:")
                    for server in enabled_servers:
                        logger.info(f"  - ID:{server.id} {server.virtual_model_name} -> {server.actual_model_name} ({server.server_url}) [优先级:{server.priority}, 权重:{server.weight}]")
                else:
                    logger.warning("没有启用的服务器!")
                
                # 记录禁用的服务器
                if disabled_servers:
                    logger.info("当前禁用的服务器:")
                    for server in disabled_servers:
                        logger.info(f"  - ID:{server.id} {server.virtual_model_name} -> {server.actual_model_name} ({server.server_url}) [优先级:{server.priority}, 权重:{server.weight}] [DISABLED]")
                else:
                    logger.info("没有禁用的服务器")
                
                # 统计虚拟模型
                virtual_models = set(s.virtual_model_name for s in enabled_servers)
                logger.info(f"虚拟模型统计: {list(virtual_models)}")
                
                result = {
                    'total_servers': len(all_servers),
                    'enabled_servers': len(enabled_servers),
                    'disabled_servers': len(disabled_servers),
                    'virtual_models': len(virtual_models)
                }
                logger.info(f"统计结果: {result}")
                return result
                
        except Exception as e:
            logger.error(f"获取服务器统计信息失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return {'total_servers': 0, 'enabled_servers': 0, 'disabled_servers': 0, 'virtual_models': 0}
    
    def reload_config(self):
        """重新加载配置"""
        logger.info("手动重新加载负载均衡器配置...")
        
        # 重新加载配置管理器
        config_manager.reload()
        
        # 更新配置参数
        self.health_check_timeout = config_manager.get('load_balancer.health_check_timeout', 3.0)
        self.max_retries = config_manager.get('load_balancer.max_retries', 3)
        
        # 显示当前状态
        stats = self.get_server_statistics()
        
        logger.info("负载均衡器配置重新加载完成")

# 全局负载均衡器实例
load_balancer = LoadBalancer()
