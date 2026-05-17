#!/bin/bash
# Abra Voice Agent — India Stack Setup Script
# Run: chmod +x setup.sh && ./setup.sh

echo ""
echo "🚀 Setting up Abra Voice Agent (Python + Exotel + Google TTS)"
echo "────────────────────────────────────────────────────────────────"

# Backend setup
cd backend

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1. Copy .env.example → .env and fill in your keys:"
echo "   cp .env.example .env"
echo ""
echo "2. Place your Google service account JSON at:"
echo "   config/google-credentials.json"
echo ""
echo "3. Expose your server to the internet (for Exotel webhooks):"
echo "   ngrok http 8000"
echo "   → Copy the https URL into .env as BASE_URL"
echo ""
echo "4. Start the backend:"
echo "   uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "5. Open the dashboard:"
echo "   Open dashboard/index.html in your browser"
echo ""
echo "────────────────────────────────────────────────────────────────"
echo "📞 Your Exotel webhook URLs to configure in Exotel dashboard:"
echo "   Call start : BASE_URL/webhook/call-start"
echo "   Call status: BASE_URL/webhook/call-status"
echo "────────────────────────────────────────────────────────────────"
