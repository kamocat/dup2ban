FROM python:3.12-slim

# Non-root user for security
RUN adduser --disabled-password --gecos "" botuser

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY bot.py .
COPY cogs/ ./cogs/

# config.json is volume-mounted at runtime (see docker-compose.yml)

USER botuser

CMD ["python", "-u", "bot.py"]
