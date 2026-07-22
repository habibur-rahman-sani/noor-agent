#!/usr/bin/env bash
# entrypoint.sh — কন্টেইনার চালু হলে (ঐচ্ছিক) GitHub থেকে সর্বশেষ কোড টেনে নেয়,
# তারপর সার্ভার চালু করে।
set -e

APP_DIR=/opt/agno_system

# ---- অটো-আপডেট (ঐচ্ছিক) ----
# .env-এ AUTO_UPDATE=1 এবং NOOR_REPO_URL=<your github repo> দিলে, কন্টেইনার
# প্রতিবার চালু হওয়ার সময় GitHub থেকে সর্বশেষ কোড টেনে নেবে।
if [ "${AUTO_UPDATE:-0}" = "1" ] && [ -n "${NOOR_REPO_URL:-}" ]; then
    echo "🔄 অটো-আপডেট: $NOOR_REPO_URL থেকে সর্বশেষ কোড আনছি..."
    rm -rf /tmp/noor_update
    if git clone --depth 1 "$NOOR_REPO_URL" /tmp/noor_update 2>/dev/null; then
        # রিপোতে অ্যাপ কোড app/ ফোল্ডারে থাকে; সেটাই $APP_DIR-এ কপি করি
        if [ -d /tmp/noor_update/app ]; then
            cp -rf /tmp/noor_update/app/. "$APP_DIR"/
        else
            cp -rf /tmp/noor_update/. "$APP_DIR"/
        fi
        rm -rf /tmp/noor_update
        echo "✅ কোড আপডেট হলো।"
        pip install -q -r "$APP_DIR/requirements-portable.txt" 2>/dev/null || true
    else
        echo "⚠️  clone ব্যর্থ (রিপো private/নেট সমস্যা?) — আগের কোড দিয়েই চলছি।"
    fi
fi

cd "$APP_DIR"
echo "🚀 Noor Agent চালু হচ্ছে → http://localhost:8000"
exec uvicorn server:app --host 0.0.0.0 --port 8000
