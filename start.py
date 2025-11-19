#!/usr/bin/env python3
"""
Ollama负载均衡代理服务启动脚本
"""

import os
import sys
import argparse
import uvicorn
import subprocess
import time
import requests
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 资源监控服务配置
RESOURCE_MONITOR_HOST = os.getenv('RESOURCE_MONITOR_HOST', 'localhost')
RESOURCE_MONITOR_PORT = int(os.getenv('RESOURCE_MONITOR_PORT', '8006'))
RESOURCE_MONITOR_URL = f"http://{RESOURCE_MONITOR_HOST}:{RESOURCE_MONITOR_PORT}"

def check_resource_monitor_service():
    """检查资源监控服务是否运行，如果没有则尝试启动"""
    try:
        # 检查服务是否响应
        response = requests.get(f"{RESOURCE_MONITOR_URL}/memory", timeout=2)
        if response.status_code == 200:
            print("✅ 资源监控服务已运行")
            return True
    except:
        pass
    
    print("🔄 资源监控服务未运行，尝试启动...")
    
    # 尝试启动systemd服务
    try:
        result = subprocess.run(['systemctl', 'is-active', 'ollama-resource-monitor'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("🚀 启动资源监控systemd服务...")
            subprocess.run(['sudo', 'systemctl', 'start', 'ollama-resource-monitor'], check=True)
            time.sleep(3)
            
            # 验证启动
            response = requests.get(f"{RESOURCE_MONITOR_URL}/memory", timeout=5)
            if response.status_code == 200:
                print("✅ 资源监控服务启动成功")
                return True
    except subprocess.CalledProcessError:
        pass
    except FileNotFoundError:
        pass
    
    # 如果systemd服务不可用，尝试直接启动
    resource_monitor_path = project_root / "resource-monitor-service"
    if resource_monitor_path.exists():
        print("🚀 直接启动资源监控服务...")
        try:
            # 在后台启动资源监控服务
            subprocess.Popen([
                sys.executable, "app.py"
            ], cwd=str(resource_monitor_path))
            
            # 等待服务启动
            for i in range(10):
                time.sleep(1)
                try:
                    response = requests.get(f"{RESOURCE_MONITOR_URL}/memory", timeout=2)
                    if response.status_code == 200:
                        print("✅ 资源监控服务启动成功")
                        return True
                except:
                    continue
        except Exception as e:
            print(f"⚠️ 无法启动资源监控服务: {e}")
    
    print("⚠️ 资源监控服务启动失败，主服务将继续运行但资源检查功能可能不可用")
    return False

def main():
    parser = argparse.ArgumentParser(description='Ollama Load Balancer Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8083, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--log-level', default='info', choices=['debug', 'info', 'warning', 'error'], help='Log level')
    parser.add_argument('--config', default='config/app.yaml', help='Configuration file path')
    parser.add_argument('--skip-resource-monitor', action='store_true', help='Skip resource monitor service startup')
    
    args = parser.parse_args()
    
    # 设置环境变量
    os.environ['CONFIG_FILE'] = args.config
    
    # 确保日志目录存在
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # 确保配置目录存在
    config_dir = project_root / 'config'
    config_dir.mkdir(exist_ok=True)
    
    print(f"Starting Ollama Load Balancer...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Config: {args.config}")
    print(f"Log Level: {args.log_level}")
    print(f"Reload: {args.reload}")
    print("-" * 50)
    
    # 检查并启动资源监控服务
    if not args.skip_resource_monitor:
        check_resource_monitor_service()
        print("-" * 50)
    
    # 启动主服务
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True,
        app_dir=str(project_root)
    )

if __name__ == "__main__":
    main()
