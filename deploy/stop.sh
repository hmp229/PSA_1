#!/bin/bash

echo "🛑 Stopping PSA Predictor..."
docker-compose -f docker-compose.simple.yml down
echo "✅ All services stopped"