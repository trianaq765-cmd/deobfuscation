FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update && apt-get install -y \
    lua5.1 \
    luajit \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone Prometheus DeobfuscatorV2
RUN git clone https://github.com/0x251/Prometheus-DeobfuscatorV2.git /app/deobfuscator
WORKDIR /app/deobfuscator

# Clone Prometheus obfuscator (required for imports)
RUN git clone https://github.com/wcrddn/Prometheus.git /app/deobfuscator/Prometheus

# Back to main app directory
WORKDIR /app

# Copy application files
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Create directories
RUN mkdir -p /app/uploads /app/outputs /app/snapshots /app/logs

# Make start script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 10000

# Start both services
CMD ["./start.sh"]
