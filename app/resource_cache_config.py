"""
资源监控配置模块（简化版）
定义模型并发检测的配置参数
"""

# 模型并发检测配置
SAME_MODEL_INTERVAL = 1200  # 相同模型调用间隔（秒）- 20分钟
MODEL_USAGE_WINDOW = 2400   # 模型使用时间窗口（秒）- 40分钟

# 模型并发配置
MODEL_CONCURRENCY_CONFIG = {
    'same_model_interval': SAME_MODEL_INTERVAL,
    'usage_window': MODEL_USAGE_WINDOW,
    'enable_concurrency_detection': True
}

