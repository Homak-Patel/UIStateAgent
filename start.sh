#!/bin/bash

echo "🚀 Starting Agent B..."
echo "📦 Building and starting all services..."
echo ""

cd docker && docker compose up --build

