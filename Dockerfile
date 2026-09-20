# FL-DDoS Detection System - Main Dockerfile
# Production-ready container for real-time DDoS detection

FROM python:3.10-slim

# Install system dependencies for packet capture
RUN apt-get update && apt-get install -y \
    libpcap-dev \
    tcpdump \
    net-tools \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ddosdfl/ ./ddosdfl/
COPY projects/ ./projects/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY models/ ./models/
COPY .env .env

# Create necessary directories
RUN mkdir -p /app/logs /app/checkpoints /app/data

# Expose ports
# 5000: Dashboard
# 8000: FL Server
# 9000: Metrics/Monitoring
EXPOSE 5000 8000 9000

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden)
CMD ["python", "-m", "ddosdfl.projects.dashboard.app"]
