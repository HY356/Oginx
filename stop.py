#!/usr/bin/env python3
"""
停止Ollama负载均衡代理服务的脚本
"""

import os
import sys
import signal
import psutil
import argparse
from pathlib import Path

def find_service_processes():
    """查找正在运行的服务进程"""
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('app.main:app' in cmd or 'start.py' in cmd for cmd in cmdline):
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    return processes

def stop_service(force=False):
    """停止服务"""
    processes = find_service_processes()
    
    if not processes:
        print("没有找到正在运行的Ollama负载均衡服务")
        return
    
    print(f"找到 {len(processes)} 个服务进程:")
    for proc in processes:
        print(f"  PID: {proc.pid}, 命令: {' '.join(proc.cmdline())}")
    
    # 尝试优雅关闭
    if not force:
        print("\n正在尝试优雅关闭服务...")
        for proc in processes:
            try:
                proc.terminate()
                print(f"  已发送终止信号给进程 {proc.pid}")
            except psutil.NoSuchProcess:
                print(f"  进程 {proc.pid} 已经不存在")
            except psutil.AccessDenied:
                print(f"  没有权限终止进程 {proc.pid}")
        
        # 等待进程结束
        import time
        time.sleep(2)
        
        # 检查是否还有进程在运行
        remaining = find_service_processes()
        if remaining:
            print(f"\n仍有 {len(remaining)} 个进程在运行，尝试强制终止...")
            force = True
    
    # 强制终止
    if force:
        print("正在强制终止服务...")
        for proc in find_service_processes():
            try:
                proc.kill()
                print(f"  已强制终止进程 {proc.pid}")
            except psutil.NoSuchProcess:
                print(f"  进程 {proc.pid} 已经不存在")
            except psutil.AccessDenied:
                print(f"  没有权限终止进程 {proc.pid}")
    
    # 最终检查
    final_processes = find_service_processes()
    if final_processes:
        print(f"\n警告: 仍有 {len(final_processes)} 个进程未能终止")
        for proc in final_processes:
            print(f"  PID: {proc.pid}")
    else:
        print("\n✓ 所有服务进程已成功停止")

def main():
    parser = argparse.ArgumentParser(description='Stop Ollama Load Balancer Service')
    parser.add_argument('--force', action='store_true', help='Force kill processes')
    
    args = parser.parse_args()
    
    print("Ollama负载均衡代理服务停止脚本")
    print("-" * 40)
    
    stop_service(force=args.force)

if __name__ == "__main__":
    main()
