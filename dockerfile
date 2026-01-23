# Use Python 3.11 slim image.
FROM python:3.11-slim

# Set working directory.
WORKDIR /app

# Set environment variables.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies.
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file.
COPY requirements.txt .

# Install Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY . .

# Create non-root user.
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Create logs directory.
RUN mkdir -p /app/logs && chown botuser:botuser /app/logs

# Health check.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; import urllib.request; \
    try: urllib.request.urlopen('http://localhost:8080/health').read(); \
    except: sys.exit(1)"

# Run bot.
CMD ["python", "main.py"]
