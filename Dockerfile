FROM python:3.11-slim

# 2) 设置容器内的工作目录（后面命令都在这个目录下执行）
WORKDIR /app

# 3) 先只复制依赖清单（利用 Docker 缓存：只要 requirements.txt 不变，这层就不重装）
COPY requirements.txt .

# 4) 在容器内装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 5) 复制你的全部代码进容器
COPY . .

# 6) 容器启动时执行的命令：用 uvicorn 跑起来
#    --host 0.0.0.0 很重要！容器里不能用 127.0.0.1（那是"只听容器内自己"）
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
