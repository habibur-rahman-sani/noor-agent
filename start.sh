#!/usr/bin/env bash
# Linux / macOS — এক কমান্ডে Noor Agent চালু করুন:  bash start.sh
set -e
cd "$(dirname "$0")"
echo "🚀 Noor Agent বিল্ড ও চালু হচ্ছে (প্রথমবার কয়েক মিনিট লাগবে)..."
docker compose up -d --build
echo ""
echo "✅ চালু হয়েছে!  ব্রাউজারে খুলুন:  http://localhost:8000"
echo "   ইউজারনেম: agno   পাসওয়ার্ড: noor12345"
echo "   লগ দেখতে:  docker compose logs -f agno"
