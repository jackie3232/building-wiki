# 工程数据发动机 · MVP —— CloudRun 容器
# 单服务全包：Flask serve 前端静态页 + /api/command（SSE 预留）
FROM python:3.11-slim

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝应用代码
COPY app.py .
COPY static ./static

# CloudRun 容器端口约定（app.py 读 PORT 环境变量决定监听端口）
ENV PORT=80
EXPOSE 80

# Flask 监听 0.0.0.0:80
CMD ["python", "app.py"]
