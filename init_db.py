#!/usr/bin/env python3
"""
数据库初始化脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import db_manager, OllamaServer
from sqlalchemy.orm import Session

def create_sample_data():
    """创建示例数据"""
    sample_servers = [
        # qwen3 模型配置
        {
            "virtual_model_name": "qwen3",
            "server_url": "http://82.157.244.136:11434",
            "actual_model_name": "qwen3:0.6b",
            "weight": 100,
            "priority": 2,
            "description": "CPU备用服务器-0.6B模型"
        },
        {
            "virtual_model_name": "qwen3",
            "server_url": "http://82.157.244.136:8004",
            "actual_model_name": "qwen3:14b",
            "weight": 30,
            "priority": 1,
            "description": "GPU服务器1-14B模型"
        },
        {
            "virtual_model_name": "qwen3",
            "server_url": "http://82.157.244.136:8004",
            "actual_model_name": "qwen3:14b",
            "weight": 70,
            "priority": 1,
            "description": "GPU服务器2-14B模型"
        }
    ]
    
    return sample_servers

def init_database():
    """初始化数据库"""
    try:
        print("正在初始化数据库...")
        
        # 初始化数据库连接
        db_manager.initialize()
        print("✓ 数据库连接建立成功")
        
        # 创建表结构
        print("✓ 数据库表结构创建成功")
        
        # 检查是否已有数据
        session = db_manager.get_session()
        try:
            existing_count = session.query(OllamaServer).count()
            
            if existing_count > 0:
                print(f"数据库中已存在 {existing_count} 条服务器配置记录")
                choice = input("是否要清空现有数据并重新插入示例数据？(y/N): ").lower()
                
                if choice == 'y':
                    # 清空现有数据
                    session.query(OllamaServer).delete()
                    session.commit()
                    print("✓ 现有数据已清空")
                else:
                    print("保留现有数据，初始化完成")
                    return
            
            # 插入示例数据
            sample_data = create_sample_data()
            for server_config in sample_data:
                server = OllamaServer(**server_config)
                session.add(server)
            
            session.commit()
            print(f"✓ 成功插入 {len(sample_data)} 条服务器配置记录")
            
            # 显示插入的数据
            print("\n插入的服务器配置:")
            print("-" * 80)
            servers = session.query(OllamaServer).all()
            for server in servers:
                print(f"ID: {server.id}")
                print(f"虚拟模型: {server.virtual_model_name}")
                print(f"服务器URL: {server.server_url}")
                print(f"实际模型: {server.actual_model_name}")
                print(f"权重: {server.weight}, 优先级: {server.priority}")
                print(f"描述: {server.description}")
                print(f"状态: {'启用' if server.is_active else '禁用'}")
                print("-" * 80)
            
        finally:
            session.close()
        
        print("🎉 数据库初始化完成！")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False
    
    return True

def show_current_config():
    """显示当前配置"""
    try:
        db_manager.initialize()
        session = db_manager.get_session()
        
        try:
            servers = session.query(OllamaServer).all()
            
            if not servers:
                print("数据库中没有服务器配置")
                return
            
            print(f"\n当前数据库中共有 {len(servers)} 条服务器配置:")
            print("=" * 100)
            
            # 按虚拟模型分组显示
            models = {}
            for server in servers:
                model_name = server.virtual_model_name
                if model_name not in models:
                    models[model_name] = []
                models[model_name].append(server)
            
            for model_name, model_servers in models.items():
                print(f"\n📋 虚拟模型: {model_name}")
                print("-" * 50)
                
                # 按优先级排序
                model_servers.sort(key=lambda x: x.priority)
                
                for server in model_servers:
                    status = "🟢 启用" if server.is_active else "🔴 禁用"
                    priority_text = "Primary" if server.priority == 1 else "Fallback"
                    
                    print(f"  {status} | {server.server_url}")
                    print(f"    实际模型: {server.actual_model_name}")
                    print(f"    权重: {server.weight}% | 优先级: {server.priority} ({priority_text})")
                    print(f"    描述: {server.description}")
                    print()
            
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ 显示配置失败: {e}")

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == 'show':
        show_current_config()
    else:
        init_database()

if __name__ == "__main__":
    main()
