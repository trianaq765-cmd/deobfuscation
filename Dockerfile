FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update && apt-get install -y \
    lua5.1 \
    luajit \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone Prometheus DeobfuscatorV2
RUN git clone https://github.com/0x251/Prometheus-DeobfuscatorV2.git /app/deobfuscator

# Clone Prometheus obfuscator
RUN git clone https://github.com/wcrddn/Prometheus.git /app/deobfuscator/Prometheus

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY config.py .
COPY server.py .
COPY bot.py .
COPY start.sh .

# Create directories
RUN mkdir -p /app/uploads /app/outputs /app/snapshots /app/logs /app/utils

# Create empty utils init
RUN touch /app/utils/__init__.py

# Make start script executable
RUN chmod +x start.sh

EXPOSE 10000

CMD ["./start.sh"]
