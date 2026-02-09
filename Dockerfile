# ChatRaw Dockerfile - Python FastAPI
FROM python:3.14-slim

WORKDIR /app

# Install build dependencies for ARM platforms
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/main.py .
COPY backend/static ./static
COPY Plugins ./Plugins

# Create data directory
RUN mkdir -p /app/data /app/data/plugins

# Environment
ENV PORT=51111
ENV DATA_DIR=/app/data

EXPOSE 51111

CMD ["python", "main.py"]
