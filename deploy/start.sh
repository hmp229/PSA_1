#!/bin/bash

echo "🚀 Starting PSA Predictor..."
echo "📁 Project: $(pwd)"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p ../backend/data

# Start services
echo "🐳 Starting containers..."
docker-compose -f docker-compose.simple.yml up -d

echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are healthy
echo "🔍 Checking service health..."
if curl -f http://localhost:8001/api/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend health check failed"
    exit 1
fi

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is healthy"
else
    echo "❌ Frontend health check failed"
    exit 1
fi

echo ""
echo "🎉 PSA Predictor is running!"
echo ""
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8001"
echo "📊 API Health: http://localhost:8001/api/health"
echo ""
echo "To stop the application: ./stop.sh"
echo "To view logs: docker-compose -f docker-compose.simple.yml logs -f"