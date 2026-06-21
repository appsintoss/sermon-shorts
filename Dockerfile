FROM python:3.11-slim

# ffmpeg 설치
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 복사
COPY app.py .

# 포트
EXPOSE 5000

# 기존 내용은 유지하시고, 마지막 CMD 전에 아래 내용을 추가하세요
RUN pip install -U yt-dlp

# 실행
CMD ["gunicorn", "--timeout", "600", "--workers", "1", "app:app"]
