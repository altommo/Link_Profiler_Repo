#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <number_of_satellites>"
    exit 1
fi

SATELLITES=$1

echo "🔄 Scaling to $SATELLITES satellite crawlers..."

# Scale satellite services
docker-compose up -d --scale satellite-1=$SATELLITES

echo "✅ Scaled to $SATELLITES satellites"
echo "📊 Check status: docker-compose ps"