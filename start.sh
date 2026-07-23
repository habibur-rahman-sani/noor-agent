#!/usr/bin/env bash
# Linux / macOS — এক কমান্ডে Noor Agent চালু করুন:  bash start.sh
set -e
cd "$(dirname "$0")"
# .env না থাকলে (যেমন GitHub থেকে clone করলে) উদাহরণ থেকে বানিয়ে নাও —
# তা না হলে docker .env-কে ফোল্ডার বানিয়ে ফেলবে (mount)। key পরে UI-র ⚙️ থেকেও দেওয়া যায়।
[ -f .env ] || { cp .env.example .env; echo "ℹ️  নতুন .env বানানো হলো (key পরে UI-র ⚙️ সেটিংস থেকে দিতে পারবেন)।"; }
echo "🚀 Noor Agent বিল্ড ও চালু হচ্ছে (প্রথমবার কয়েক মিনিট লাগবে)..."
docker compose up -d --build
echo ""
echo "✅ চালু হয়েছে!  ব্রাউজারে খুলুন:  http://localhost:8000"
echo "   ইউজারনেম: agno   পাসওয়ার্ড: noor12345"
echo "   লগ দেখতে:  docker compose logs -f agno"
