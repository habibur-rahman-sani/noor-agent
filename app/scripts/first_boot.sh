#!/usr/bin/env bash
# first_boot.sh — MongoDB কন্টেইনার সেটআপ + Playwright ব্রাউজার ইনস্টল, শুধু
# প্রথমবার আসল বুটে চলে (build-time chroot-এ Docker ডিমন চলে না বলে এটা ISO
# বিল্ডের বদলে প্রথম বুটে করা হয় — তার মানে প্রথমবার চালু হতে ইন্টারনেট লাগবে)।
set -e

MARKER=/var/lib/agno-first-boot-done
PROJECT_DIR=/opt/agno_system

if [ -f "$MARKER" ]; then
    exit 0
fi

# ---- MongoDB (ডকার) ----
for i in $(seq 1 30); do
    docker info >/dev/null 2>&1 && break
    sleep 1
done

if ! docker ps -aq -f name=^agno-mongo$ | grep -q .; then
    docker run -d --name agno-mongo --restart unless-stopped -p 27017:27017 mongo || \
        echo "⚠️  MongoDB কন্টেইনার চালু করা যায়নি — ইন্টারনেট কানেকশন আছে কিনা যাচাই করো, পরে ম্যানুয়ালি চেষ্টা করা যাবে।"
fi

# ---- ফায়ারওয়াল (ufw) — build-time chroot-এ netfilter rule বসানো যায় না (কোনো
#      চলমান কার্নেল নেটওয়ার্ক স্ট্যাক নেই), তাই Docker-এর মতো এটাও প্রথম বুটে করা
#      হচ্ছে। ডিফল্ট নীতি: সব ইনকামিং বন্ধ, শুধু 8000 (ওয়েব UI, এখন পাসওয়ার্ড-সুরক্ষিত)
#      খোলা — যাতে একই WiFi/LAN-এর অন্য ডিভাইস থেকেও ড্যাশবোর্ড অ্যাক্সেস করা যায়। ----
if command -v ufw >/dev/null 2>&1; then
    ufw default deny incoming >/dev/null 2>&1 || true
    ufw default allow outgoing >/dev/null 2>&1 || true
    ufw allow 8000/tcp comment 'Agno System web UI' >/dev/null 2>&1 || true
    ufw --force enable || \
        echo "⚠️  ufw চালু করা যায়নি — ম্যানুয়ালি 'sudo ufw enable' চালাও।"
fi

# ---- Playwright ব্রাউজার (Browser Agent-এর জন্য, সম্পূর্ণ ফ্রি — কোনো
#      BrowserBase/AgentQL পেইড key ছাড়াই real ক্লিক/ফর্ম-ফিলাপ সম্ভব করতে) ----
if [ -x "$PROJECT_DIR/venv/bin/python" ]; then
    sudo -u agno "$PROJECT_DIR/venv/bin/python" -m playwright install --with-deps chromium 2>&1 | tail -20 || \
        echo "⚠️  Playwright ব্রাউজার ইনস্টল করা যায়নি — পরে ম্যানুয়ালি: 'venv/bin/python -m playwright install --with-deps chromium'"
fi

touch "$MARKER"

echo ""
echo "==================== প্রথম বুট সেটআপ শেষ ===================="
echo "ঐচ্ছিক (কিন্তু সুপারিশকৃত) পরের ধাপ — টার্মিনালে/ডেস্কটপ থেকে করো:"
echo ""
echo "১) রোলব্যাক-সুরক্ষা (Timeshift) সেটআপ করো (একবারই, ইন্টারেক্টিভ):"
echo "     sudo timeshift --setup"
echo "   এটা না করলে PC/Linux System Agent রিস্কি কাজের আগে স্ন্যাপশট নিতে পারবে না"
echo "   (কাজ আটকাবে না, শুধু রোলব্যাক-সুরক্ষা ছাড়া এগোবে)।"
echo ""
echo "২) সম্পূর্ণ অফলাইন/লোকাল মোড চাইলে (ইন্টারনেট/OPENROUTER_API_KEY ছাড়াই):"
echo "     curl -fsSL https://ollama.com/install.sh | sh"
echo "     ollama pull qwen2.5:7b"
echo "     ollama pull qwen2.5-coder:7b"
echo "   তারপর $PROJECT_DIR/.env-এ LOCAL_MODEL_MODE=1 বসাও ও সার্ভিস রিস্টার্ট করো:"
echo "     sudo systemctl restart agno-system"
echo "================================================================"
