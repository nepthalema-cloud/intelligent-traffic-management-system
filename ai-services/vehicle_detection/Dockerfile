FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    libgl1-mesa-glx ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8n model
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

COPY src/ ./src/

CMD ["python", "src/main.py"]
