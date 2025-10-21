FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# 기본 명령어 (docker-compose에서 오버라이드)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]