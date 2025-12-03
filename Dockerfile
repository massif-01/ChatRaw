# ChatRaw Dockerfile - Python FastAPI
FROM python:3.12-slim

WORKDIR /app

# Install dependencies with retry and trusted hosts
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt || \
    pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt || \
    pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy application
COPY backend/main.py .
COPY backend/static ./static

# Create data directory
RUN mkdir -p /app/data

# Environment
ENV PORT=51111
ENV DATA_DIR=/app/data

EXPOSE 51111

CMD ["python", "main.py"]
