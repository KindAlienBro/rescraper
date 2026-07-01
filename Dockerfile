FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the HF Spaces port
EXPOSE 7860

# Run with gunicorn for production (1 worker to ensure global queue is shared)
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "300", "--workers", "1", "--threads", "4", "app:app"]
