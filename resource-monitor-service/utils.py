import platform
import subprocess
import shutil
import os

def detect_os():
    """检测操作系统类型"""
    system = platform.system().lower()
    return {
        'os': system,
        'is_windows': system == 'windows',
        'is_linux': system == 'linux',
        'is_macos': system == 'darwin'
    }

def find_nvidia_smi():
    """跨平台查找nvidia-smi命令"""
    os_info = detect_os()
    
    if os_info['is_windows']:
        # Windows常见路径
        possible_paths = [
            'nvidia-smi.exe',
            'nvidia-smi',
            r'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe',
            r'C:\Windows\System32\nvidia-smi.exe',
            r'C:\Program Files (x86)\NVIDIA Corporation\NVSMI\nvidia-smi.exe'
        ]
        
        # 首先检查PATH中是否存在
        if shutil.which('nvidia-smi'):
            return 'nvidia-smi'
        
        # 检查具体路径
        for path in possible_paths:
            if os.path.isfile(path):
                return path
                
        return None
    else:
        # Linux/macOS
        return shutil.which('nvidia-smi')

def run_cross_platform_command(cmd, timeout=10):
    """跨平台执行命令"""
    os_info = detect_os()
    
    try:
        # Windows可能需要shell=True
        shell_mode = os_info['is_windows']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell_mode
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f'Command timeout after {timeout} seconds'
        }
    except FileNotFoundError:
        return {
            'success': False,
            'error': 'Command not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
