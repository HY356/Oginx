from flask import Flask, jsonify
import psutil
import subprocess
import json
import logging
import platform
import os
from datetime import datetime
from platform_utils import (
    get_platform_info, 
    find_nvidia_smi_cross_platform, 
    execute_command_cross_platform,
    get_memory_usage_cross_platform
)

app = Flask(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 检测操作系统
OS_INFO = get_platform_info()
SYSTEM_OS = OS_INFO['system'].lower()

def get_memory_info():
    """获取系统内存信息 - 跨平台兼容"""
    try:
        # 使用跨平台内存获取函数
        memory_data = get_memory_usage_cross_platform()
        if memory_data is None:
            return None
            
        # 简化返回格式，保持向后兼容
        physical = memory_data['physical_memory']
        return {
            "total_gb": physical['total_gb'],
            "available_gb": physical['available_gb'],
            "used_gb": physical['used_gb'],
            "percentage": physical['percentage'],
            "system_os": memory_data['platform'],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取内存信息失败: {e}")
        return None

def get_gpu_memory_info():
    """获取GPU显存信息 - 跨平台兼容"""
    try:
        nvidia_smi_cmd = find_nvidia_smi_cross_platform()
        
        if nvidia_smi_cmd is None:
            return {"error": f"nvidia-smi not found on {SYSTEM_OS}. Please install NVIDIA drivers."}
        
        # 构建命令
        cmd = [
            nvidia_smi_cmd,
            '--query-gpu=memory.total,memory.used,memory.free', 
            '--format=csv,noheader,nounits'
        ]
        
        # 使用跨平台命令执行函数
        result = execute_command_cross_platform(cmd, timeout=10)
        
        if not result['success']:
            return {"error": f"nvidia-smi failed: {result.get('error', 'Unknown error')}"}
        
        gpu_info = []
        lines = result['stdout'].strip().split('\n')
        
        for i, line in enumerate(lines):
            if line.strip():
                try:
                    # 处理不同的分隔符格式
                    parts = line.replace(',', ' ').split()
                    if len(parts) >= 3:
                        total, used, free = map(int, parts[:3])
                        gpu_info.append({
                            "gpu_id": i,
                            "total_mb": total,
                            "used_mb": used,
                            "free_mb": free,
                            "total_gb": round(total / 1024, 2),
                            "used_gb": round(used / 1024, 2),
                            "free_gb": round(free / 1024, 2),
                            "usage_percentage": round((used / total) * 100, 2) if total > 0 else 0
                        })
                except (ValueError, IndexError) as e:
                    logger.warning(f"解析GPU数据失败 (line: {line}): {e}")
                    continue
        
        if not gpu_info:
            return {"error": "No valid GPU data found"}
        
        return {
            "gpus": gpu_info,
            "total_gpus": len(gpu_info),
            "system_info": get_system_info(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取GPU信息失败: {e}")
        return {"error": f"Failed to get GPU info: {str(e)}"}

def get_system_info():
    """获取系统基本信息"""
    return {
        "os": SYSTEM_OS,
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "cpu_count": psutil.cpu_count(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "os_info": OS_INFO
    }

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "service": "resource-monitor",
        "system_info": get_system_info(),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/memory', methods=['GET'])
def get_memory():
    """查询系统内存剩余接口"""
    memory_info = get_memory_info()
    
    if memory_info is None:
        return jsonify({"error": "Failed to get memory information"}), 500
    
    return jsonify({
        "status": "success",
        "data": memory_info
    })

@app.route('/gpu-memory', methods=['GET'])
def get_gpu_memory():
    """查询GPU显存剩余接口"""
    gpu_info = get_gpu_memory_info()
    
    if "error" in gpu_info:
        return jsonify({
            "status": "error",
            "message": gpu_info["error"]
        }), 500
    
    return jsonify({
        "status": "success",
        "data": gpu_info
    })

@app.route('/resource-check', methods=['POST'])
def resource_check():
    """检查资源是否足够的接口"""
    from flask import request
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    
    server_type = data.get('type', '').upper()  # CPU 或 GPU
    required_performance = data.get('performance', 0)  # 需要的性能(GB)
    
    if server_type not in ['CPU', 'GPU']:
        return jsonify({"error": "Invalid server type. Must be 'CPU' or 'GPU'"}), 400
    
    if required_performance <= 0:
        return jsonify({"error": "Performance requirement must be greater than 0"}), 400
    
    result = {
        "server_type": server_type,
        "required_gb": required_performance,
        "sufficient": False,
        "available_gb": 0,
        "timestamp": datetime.now().isoformat()
    }
    
    if server_type == 'CPU':
        memory_info = get_memory_info()
        if memory_info:
            result["available_gb"] = memory_info["available_gb"]
            result["sufficient"] = memory_info["available_gb"] >= required_performance
            result["details"] = memory_info
    
    elif server_type == 'GPU':
        gpu_info = get_gpu_memory_info()
        if "error" not in gpu_info and gpu_info.get("gpus"):
            # 找到可用显存最多的GPU
            max_free_gpu = max(gpu_info["gpus"], key=lambda x: x["free_gb"])
            result["available_gb"] = max_free_gpu["free_gb"]
            result["sufficient"] = max_free_gpu["free_gb"] >= required_performance
            result["details"] = gpu_info
            result["recommended_gpu"] = max_free_gpu["gpu_id"]
        else:
            result["error"] = gpu_info.get("error", "No GPU information available")
    
    return jsonify({
        "status": "success",
        "data": result
    })

if __name__ == '__main__':
    from config_loader import config_loader
    
    # 从配置文件获取设置
    host = config_loader.get_host()
    port = config_loader.get_port()
    device_type = config_loader.get_device_type()
    
    logger.info(f"🚀 启动资源监控服务: 设备类型={device_type}, 端口={port}")
    app.run(host=host, port=port, debug=True)
