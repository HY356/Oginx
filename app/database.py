"""
数据库模型和连接管理
"""

import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

class OllamaServer(Base):
    """Ollama服务器配置模型"""
    __tablename__ = 'ollama_servers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    virtual_model_name = Column(String(100), nullable=False, comment='虚拟模型名称')
    server_url = Column(String(255), nullable=False, comment='服务器URL')
    actual_model_name = Column(String(100), nullable=False, comment='实际模型名称')
    weight = Column(Integer, default=100, comment='权重')
    priority = Column(Integer, default=1, comment='优先级(1=primary, 2=fallback)')
    type = Column(String(20), nullable=False, comment='服务器类型(CPU/GPU)')
    performance = Column(Integer, default=8, comment='模型所需性能(GB)')
    skip_resource_check = Column(Boolean, default=False, comment='是否跳过资源检测')
    is_active = Column(Boolean, default=True, comment='是否启用')
    description = Column(Text, comment='描述信息')
    count = Column(Integer, default=0, comment='访问次数统计')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f"<OllamaServer(virtual_model='{self.virtual_model_name}', server='{self.server_url}', priority={self.priority})>"

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def initialize(self, database_url: str = None):
        """初始化数据库连接"""
        if database_url is None:
            database_url = os.getenv('DATABASE_URL', 'mysql+pymysql://root:hedong2018@172.21.32.3:3306/hetengwx')
        
        try:
            self.engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False
            )
            
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # 创建所有表
            Base.metadata.create_all(bind=self.engine)
            
            self._initialized = True
            logger.info("数据库连接初始化成功")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        if not self._initialized:
            raise RuntimeError("数据库未初始化，请先调用initialize()方法")
        return self.SessionLocal()
    
    @contextmanager
    def get_db_session(self):
        """获取数据库会话的上下文管理器"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()
    
    def increment_server_count(self, server_id: int):
        """增加服务器访问计数"""
        try:
            with self.get_db_session() as session:
                server = session.query(OllamaServer).filter(OllamaServer.id == server_id).first()
                if server:
                    server.count = (server.count or 0) + 1
                    session.commit()
                    logger.debug(f"服务器 {server.server_url} 访问计数增加到 {server.count}")
                else:
                    logger.warning(f"未找到ID为 {server_id} 的服务器")
        except Exception as e:
            logger.error(f"更新服务器访问计数失败: {e}")
    
    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            logger.info("数据库连接已关闭")

# 全局数据库管理器实例
db_manager = DatabaseManager()
