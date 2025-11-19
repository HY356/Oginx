# 资源监控服务 (Resource Monitor Service)

独立的资源监控微服务，提供系统内存和GPU显存查询功能，用于Ollama负载均衡系统的智能服务器切换。

## 功能特性

- **内存监控**: 查询系统内存使用情况和剩余容量
- **GPU显存监控**: 查询NVIDIA GPU显存使用情况和剩余容量
- **资源检查**: 根据服务器类型和性能需求判断资源是否充足
- **RESTful API**: 提供标准的HTTP接口

## API接口

### 1. 健康检查
```
GET /health
```

### 2. 查询内存信息
```
GET /memory
```
返回系统内存的总量、已用、可用容量等信息。

### 3. 查询GPU显存信息
```
GET /gpu-memory
```
返回所有GPU的显存使用情况。

### 4. 资源充足性检查
```
POST /resource-check
Content-Type: application/json

{
    "type": "CPU",           // 服务器类型: "CPU" 或 "GPU"
    "performance": 8         // 需要的性能(GB)
}
```

## 安装和运行

### Windows系统
```cmd
# 双击运行或在命令行执行
start.bat
```

### Linux/macOS系统
```bash
# 添加执行权限并运行
chmod +x start.sh
./start.sh
```

### 手动启动
```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python start.py
```

服务将在 `http://localhost:8006` 启动。

### Docker部署
```bash
# 构建镜像
docker build -f docker/Dockerfile -t resource-monitor .

# 运行容器
docker run -p 8006:8006 resource-monitor

# 或使用docker-compose
cd docker && docker-compose up -d
```

### 生产环境部署
```bash
gunicorn -w 4 -b 0.0.0.0:8006 app:app
```

## 使用示例

### 检查CPU服务器资源
```bash
curl -X POST http://localhost:8006/resource-check \
  -H "Content-Type: application/json" \
  -d '{"type": "CPU", "performance": 8}'
```

### 检查GPU服务器资源
```bash
curl -X POST http://localhost:8006/resource-check \
  -H "Content-Type: application/json" \
  -d '{"type": "GPU", "performance": 12}'
```

## 系统要求

- **Python 3.7+** (Windows/Linux/macOS)
- **内存监控**: 无额外要求，使用psutil库
- **GPU监控**: NVIDIA GPU + NVIDIA驱动 + nvidia-smi工具
- 足够的系统权限读取硬件信息

## 跨平台兼容性

### ✅ 支持的操作系统
- **Windows 10/11** - 完全支持
- **Linux** (Ubuntu, CentOS, RHEL等) - 完全支持  
- **macOS** - 支持内存监控，GPU监控需NVIDIA GPU

### 🔧 平台特定配置
- **Windows**: 自动检测nvidia-smi.exe路径
- **Linux**: 使用标准nvidia-smi命令
- **所有平台**: 使用psutil进行内存监控

## 注意事项

- GPU监控需要NVIDIA GPU和相应驱动
- 服务默认运行在8006端口，避免与主应用冲突
- Windows和Linux使用不同的启动脚本
- 建议在生产环境使用gunicorn等WSGI服务器
- Docker部署可确保跨平台一致性
