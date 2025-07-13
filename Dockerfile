FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install system dependencies and Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev ffmpeg && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    apt-get purge -y gcc && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Copy the rest of the app
COPY . .

# Expose port 8888 for FastAPI
EXPOSE 8888

# Run using Gunicorn with Uvicorn workers on port 8888
CMD ["gunicorn", "app:app", \
     "--workers=8", \
     "--worker-class=uvicorn.workers.UvicornWorker", \
     "--bind=0.0.0.0:8888"]
