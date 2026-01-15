#!/bin/bash

echo "Starting Prometheus Deobfuscator Services..."

# Create necessary directories
mkdir -p /app/uploads /app/outputs /app/snapshots /app/logs

# Start web server in background
echo "Starting Web Server on port 10000..."
gunicorn --bind 0.0.0.0:10000 --workers 2 --timeout 120 server:app &
WEB_PID=$!

# Wait a moment for web server to start
sleep 3

# Start Discord bot
echo "Starting Discord Bot..."
python3 bot.py &
BOT_PID=$!

echo "Services started!"
echo "Web Server PID: $WEB_PID"
echo "Discord Bot PID: $BOT_PID"

# Keep container running and handle signals
trap "kill $WEB_PID $BOT_PID 2>/dev/null; exit" SIGTERM SIGINT

# Wait for any process to exit
wait -n

# If any process exits, kill the other and exit
kill $WEB_PID $BOT_PID 2>/dev/null
exit $?
