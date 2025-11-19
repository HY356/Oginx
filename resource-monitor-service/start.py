#!/usr/bin/env python3
"""
资源监控服务启动脚本
"""
import os
import sys
from app import app
from config import Config

def main():
    """启动资源监控服务"""
    print(f"启动资源监控服务...")
    print(f"服务地址: http://{Config.HOST}:{Config.PORT}")
    print(f"调试模式: {Config.DEBUG}")
    print("=" * 50)
    
    try:
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=Config.DEBUG
        )
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"服务启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
