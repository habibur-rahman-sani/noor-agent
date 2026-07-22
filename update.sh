#!/usr/bin/env bash
# GitHub থেকে সর্বশেষ কোড এনে Noor Agent আপডেট করুন:  bash update.sh
set -e
cd "$(dirname "$0")"
if [ -d .git ]; then
    echo "🔄 GitHub থেকে সর্বশেষ কোড আনছি..."
    git pull --ff-only
fi
echo "🔁 নতুন কোড দিয়ে রিবিল্ড ও রিস্টার্ট..."
docker compose up -d --build
echo "✅ আপডেট শেষ। http://localhost:8000"
