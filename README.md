# Ollama 负载均衡代理系统

一个功能完整的Ollama模型推理服务负载均衡系统，支持多服务器智能调度、资源感知、并发控制和故障转移。

## 🌟 核心特性

### 智能负载均衡
- **多优先级调度**：支持主服务器(priority=1)和备用服务器(priority=2)的智能切换
- **权重分配**：基于权重的流量分配，支持灵活的负载分配策略
- **健康检查**：定期检测服务器健康状态，自动隔离故障节点
- **自动故障转移**：服务器故障时自动切换到备用服务器

### 资源感知调度
- **实时资源监控**：独立的资源监控微服务，支持CPU和GPU服务器
- **内存/显存检查**：在请求前检查资源是否充足，避免OOM
- **智能缓存机制**：根据服务器稳定性动态调整缓存时间
- **并发感知**：同一模型的并发请求智能判断，避免重复资源检查

### 高可用性
- **多层容错**：健康检查→并发检测→缓存检查→资源检查→请求代理
- **请求重试**：支持配置最大重试次数，自动切换服务器重试
- **详细日志**：完整的请求日志、性能日志、错误日志
- **监控指标**：提供Prometheus兼容的指标接口

### 管理接口
- **服务器管理**：增删改查Ollama服务器配置
- **模型管理**：虚拟模型与实际模型的映射管理
- **资源缓存管理**：查看缓存统计、清空缓存
- **优先级检查**：查看指定模型会使用的服务器优先级

## 📋 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    客户端请求                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              主服务 (FastAPI, 端口8083)                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 1. 健康检查 - 检查服务器是否在线                          │ │
│  │ 2. 并发检测 - 判断是否需要资源检查                        │ │
│  │ 3. 缓存检查 - 查询资源检查缓存                            │ │
│  │ 4. 资源检查 - 调用资源监控服务检查资源                    │ │
│  │ 5. 请求代理 - 转发请求到Ollama服务器                     │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼────┐  ┌──────▼──────┐  ┌──▼──────────┐
│  Ollama    │  │  Ollama     │  │  Ollama     │
│ 服务器 1   │  │  服务器 2   │  │  服务器 3   │
│ (GPU)      │  │  (GPU)      │  │  (CPU)      │
└────────────┘  └─────────────┘  └─────────────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  资源监控服务 (Flask)        │
        │  - CPU内存监控 (端口8005)   │
        │  - GPU显存监控 (端口8006)   │
        └─────────────────────────────┘
```

## 🚀 快速开始

### 前置要求
- Python 3.8+
- MySQL 5.7+ 或 MySQL 8.0+
- 至少一个Ollama服务器实例

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd oginx
```

2. **配置环境变量**
```bash
# 复制配置模板
cp .env.example .env

# 编辑.env文件，配置数据库连接
# 修改 DATABASE_URL 为实际的数据库地址
```

3. **配置应用参数**
```bash
# 编辑 config/app.yaml，根据需要调整参数
# 主要配置项：
# - server.port: 服务端口（默认8083）
# - database.url: 数据库连接（必须配置）
# - load_balancer: 负载均衡参数
# - logging: 日志配置
```

4. **安装依赖**
```bash
pip install -r requirements.txt
pip install -r resource-monitor-service/requirements.txt
```

5. **初始化数据库**

#### 方式一：使用SQL文件（推荐）
```bash
# 使用MySQL客户端导入SQL文件
mysql -u username -p database_name < ollama_servers.sql

# 或在MySQL中执行
mysql> source ollama_servers.sql;
```

#### 方式二：使用Python脚本
```bash
python init_db.py
```

6. **启动服务**
```bash
# 启动主服务和资源监控服务
python start.py

# 或指定参数启动
python start.py --host 0.0.0.0 --port 8083 --log-level info
```

7. **停止服务**
```bash
python stop.py
```

## 📖 配置说明

### .env 文件
```env
# 数据库连接字符串
DATABASE_URL=mysql+pymysql://username:password@host:port/database

# 日志级别
LOG_LEVEL=INFO

# 服务端口
SERVER_PORT=8083

# 配置文件路径
CONFIG_FILE=config/app.yaml
```

### config/app.yaml 主要配置

```yaml
# 服务器配置
server:
  host: "0.0.0.0"
  port: 8083
  workers: 1

# 数据库配置
database:
  url: "mysql+pymysql://username:password@host:port/database"
  pool_size: 10
  max_overflow: 20
  pool_recycle: 3600

# 负载均衡配置
load_balancer:
  health_check_timeout: 1.0      # 健康检查超时(秒)
  config_cache_ttl: 10           # 配置缓存时间(秒)
  db_check_interval: 5           # 数据库变更检查间隔(秒)
  max_retry_count: 2             # 最大重试次数
  concurrent_health_checks: true # 并发健康检查

# HTTP客户端配置
http_client:
  timeout: 300.0                 # 请求超时(秒)
  max_connections: 100           # 最大连接数
  max_keepalive_connections: 20  # 最大保持连接数

# 日志配置
logging:
  level: "INFO"
  enable_request_log: true
  enable_performance_log: true
  log_file_max_size: "100MB"
  log_file_backup_count: 10
  log_format: "detailed"
  real_time_flush: true
  flush_interval: 1
  files:
    app: "logs/app.log"
    request: "logs/request.log"
    error: "logs/error.log"
    performance: "logs/performance.log"
    health: "logs/health.log"

# 监控配置
monitoring:
  enable_metrics: true
  metrics_endpoint: "/metrics"
  health_endpoint: "/health"
  status_endpoint: "/status"
```

### resource-monitor-service/config.yaml

```yaml
# 设备类型配置
device:
  type: "CPU"  # CPU 或 GPU
  port:
    cpu: 8005
    gpu: 8006

# 服务配置
service:
  host: "0.0.0.0"
  timeout: 30
  log_level: "INFO"

# 资源监控配置
monitoring:
  memory_threshold: 90           # 内存阈值(%)
  gpu_memory_threshold: 90       # 显存阈值(%)
  check_interval: 5              # 监控间隔(秒)

# 缓存配置
cache:
  enabled: true
  expire_time: 30                # 缓存过期时间(秒)
```

## 🔌 API 接口

### 模型推理接口

#### POST /v1/chat/completions
发送聊天完成请求

```bash
curl -X POST http://localhost:8083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

#### POST /api/generate
发送生成请求

```bash
curl -X POST http://localhost:8083/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "prompt": "Hello"
  }'
```

### 管理接口

#### 获取所有服务器配置
```bash
GET /admin/servers
```

#### 添加服务器
```bash
POST /admin/servers
Content-Type: application/json

{
  "virtual_model_name": "qwen3",
  "server_url": "http://localhost:11434",
  "actual_model_name": "qwen3:14b",
  "weight": 100,
  "priority": 1,
  "type": "GPU",
  "performance": 24,
  "description": "GPU服务器"
}
```

#### 更新服务器
```bash
PUT /admin/servers/{server_id}
```

#### 删除服务器
```bash
DELETE /admin/servers/{server_id}
```

#### 查看资源缓存统计
```bash
GET /admin/resource-cache/stats
```

#### 清空资源缓存
```bash
POST /admin/resource-cache/clear
```

#### 检查模型优先级
```bash
GET /admin/server-priority/check/{model_name}
```

#### 获取优先级分布概览
```bash
GET /admin/server-priority/overview
```

### 监控接口

#### 健康检查
```bash
GET /health
```

#### 系统状态
```bash
GET /status
```

#### Prometheus指标
```bash
GET /metrics
```

## 📊 权重(weight)与优先级(priority)的区别

### 优先级(Priority)
- **作用**：决定服务器的使用顺序
- **值**：1(主要), 2(备用), 其他
- **逻辑**：
  - 优先使用priority=1的服务器
  - 如果priority=1的服务器都不可用，则使用priority=2的服务器
  - 支持多个priority=1的服务器并发使用

### 权重(Weight)
- **作用**：在同一优先级内分配流量比例
- **值**：正整数(如30, 70, 100)
- **逻辑**：
  - 在同一优先级的服务器中，按权重比例分配请求
  - 权重为30和70的两个服务器，流量比例为30:70
  - 权重值本身无特殊含义，只是相对比例

### 应用场景

**场景1：主备模式**
```
priority=1: GPU服务器1 (weight=100)  → 处理所有请求
priority=2: CPU服务器  (weight=100)  → GPU故障时接管
```

**场景2：负载均衡**
```
priority=1: GPU服务器1 (weight=30)   → 30%流量
priority=1: GPU服务器2 (weight=70)   → 70%流量
priority=2: CPU服务器  (weight=100)  → 两个GPU都故障时接管
```

**场景3：复杂任务分流**
```
priority=1: GPU服务器  (weight=100)  → 复杂任务
priority=2: CPU服务器  (weight=100)  → 简单任务
```

## 🔧 数据库表结构

### ollama_servers 表

表结构定义在 `ollama_servers.sql` 文件中，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键，自增 |
| virtual_model_name | VARCHAR(100) | 虚拟模型名称 |
| server_url | VARCHAR(255) | 服务器URL |
| actual_model_name | VARCHAR(100) | 实际模型名称 |
| weight | INT | 权重，用于同优先级内的流量分配 |
| priority | INT | 优先级(1=主要, 2=备用) |
| type | VARCHAR(255) | 服务器类型(CPU/GPU) |
| performance | INT | 模型所需资源大小(GB) |
| description | TEXT | 描述信息 |
| is_active | TINYINT | 是否启用(0/1) |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| count | INT | 计数 |
| skip_resource_check | TINYINT | 是否跳过资源检测(0/1) |

### SQL文件说明

项目提供了 `ollama_servers.sql` 文件，包含完整的表结构定义。

**导入方式：**
```bash
# 方式1：使用mysql命令行
mysql -u username -p database_name < ollama_servers.sql

# 方式2：在MySQL客户端中执行
mysql> USE database_name;
mysql> source ollama_servers.sql;

# 方式3：使用MySQL Workbench或其他GUI工具导入
```

**注意事项：**
- 确保数据库已创建，SQL文件会自动创建表
- 表使用 `utf8mb4` 字符集，支持中文
- 使用 `InnoDB` 引擎，支持事务

## 📝 日志说明

系统生成以下日志文件：

- **logs/app.log** - 应用日志，记录系统运行信息
- **logs/request.log** - 请求日志，记录所有API请求
- **logs/error.log** - 错误日志，记录系统错误
- **logs/performance.log** - 性能日志，记录请求耗时
- **logs/health.log** - 健康检查日志，记录服务器状态变化

## 🐛 故障排查

### 问题：无法连接数据库
**解决方案**：
1. 检查`.env`文件中的`DATABASE_URL`是否正确
2. 确保MySQL服务正在运行
3. 验证数据库用户名和密码
4. 检查防火墙是否允许连接

### 问题：资源监控服务启动失败
**解决方案**：
1. 确保已安装`resource-monitor-service/requirements.txt`中的依赖
2. 检查端口8005/8006是否被占用
3. 查看`resource-monitor-service`的日志文件

### 问题：请求转发到Ollama失败
**解决方案**：
1. 检查Ollama服务器是否在线
2. 验证`server_url`配置是否正确
3. 确保网络连接正常
4. 查看`logs/error.log`了解详细错误信息

## 📚 相关文档

- [系统逻辑设计](./SYSTEM_LOGIC_DESIGN.md) - 详细的系统设计和流程说明
- [管理接口文档](./ADMIN_MANAGEMENT.md) - 完整的管理接口说明
- [部署指南](./README_DEPLOY.md) - 生产环境部署指南
- [代码逻辑验证](./code_logic_verification.md) - 代码与设计的一致性验证

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📞 联系方式

如有问题或建议，请提交Issue或联系项目维护者。
