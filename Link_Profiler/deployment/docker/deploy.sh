#!/bin/bash

echo "🚀 Deploying Link Profiler Distributed System..."

# Build and start services
docker-compose down
docker-compose build
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
docker-compose ps

# Test Redis connection
echo "📊 Testing Redis connection..."
docker-compose exec redis redis-cli ping

# Test PostgreSQL connection
echo "🗄️ Testing PostgreSQL connection..."
docker-compose exec postgres pg_isready -U postgres

# Test API health
echo "🌐 Testing API health..."
curl -f http://localhost:8000/health || echo "API not ready yet"

echo "✅ Deployment complete!"
echo "🌐 API available at: http://localhost:8000"
echo "📊 Queue stats: http://localhost:8000/queue/stats"
echo "📖 API docs: http://localhost:8000/docs"
echo "📊 Monitoring: http://localhost:8001"