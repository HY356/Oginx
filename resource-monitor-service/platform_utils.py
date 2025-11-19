"""
跨平台工具函数模块
提供Windows和Linux系统的兼容性支持
"""
import platform
import subprocess
import shutil
import os
import logging

logger = logging.getLogger(__name__)

def get_platform_info():
    """获取详细的平台信息"""
    system = platform.system()
    return {
        'system': system,
        'is_windows': system == 'Windows',
        'is_linux': system == 'Linux',
        'is_macos': system == 'Darwin',
        'machine': platform.machine(),
        'processor': platform.processor(),
        'release': platform.release(),
        'version': platform.version()
    }

def find_nvidia_smi_cross_platform():
    """跨平台查找nvidia-smi命令"""
    platform_info = get_platform_info()
    
    if platform_info['is_windows']:
        # Windows系统的nvidia-smi可能位置
        windows_paths = [
            'nvidia-smi.exe',
            'nvidia-smi',
            r'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe',
            r'C:\Windows\System32\nvidia-smi.exe',
            r'C:\Program Files (x86)\NVIDIA Corporation\NVSMI\nvidia-smi.exe'
        ]
        
        # 首先检查PATH环境变量
        if shutil.which('nvidia-smi'):
            return 'nvidia-smi'
        
        # 检查具体路径
        for path in windows_paths:
            if os.path.isfile(path):
                logger.info(f"找到nvidia-smi: {path}")
                return path
        
        logger.warning("Windows系统未找到nvidia-smi")
        return None
        
    else:
        # Linux/macOS系统
        nvidia_smi_path = shutil.which('nvidia-smi')
        if nvidia_smi_path:
            logger.info(f"找到nvidia-smi: {nvidia_smi_path}")
            return nvidia_smi_path
        
        logger.warning(f"{platform_info['system']}系统未找到nvidia-smi")
        return None

def execute_command_cross_platform(cmd, timeout=10, shell=None):
    """跨平台执行命令"""
    platform_info = get_platform_info()
    
    try:
        # 自动判断是否需要shell模式
        if shell is None:
            shell = platform_info['is_windows']
        
        logger.debug(f"执行命令: {cmd}, shell={shell}, 平台: {platform_info['system']}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            encoding='utf-8',
            errors='replace'  # 处理编码错误
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode,
            'platform': platform_info['system']
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f'命令超时 ({timeout}秒)',
            'platform': platform_info['system']
        }
    except FileNotFoundError as e:
        return {
            'success': False,
            'error': f'命令未找到: {e}',
            'platform': platform_info['system']
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'执行命令失败: {e}',
            'platform': platform_info['system']
        }

def get_memory_usage_cross_platform():
    """跨平台获取内存使用情况"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            'physical_memory': {
                'total_bytes': memory.total,
                'available_bytes': memory.available,
                'used_bytes': memory.used,
                'free_bytes': memory.free,
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
                'used_gb': round(memory.used / (1024**3), 2),
                'percentage': memory.percent
            },
            'swap_memory': {
                'total_bytes': swap.total,
                'used_bytes': swap.used,
                'free_bytes': swap.free,
                'total_gb': round(swap.total / (1024**3), 2),
                'used_gb': round(swap.used / (1024**3), 2),
                'free_gb': round(swap.free / (1024**3), 2),
                'percentage': swap.percent
            },
            'platform': get_platform_info()['system']
        }
    except Exception as e:
        logger.error(f"获取内存信息失败: {e}")
        return None
