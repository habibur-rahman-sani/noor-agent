#!/usr/bin/env bash
# sudoers-এর বিকল্প হিসেবে polkit rule বসানো (শুধু systemd সার্ভিস কন্ট্রোলের জন্য)।
# প্যাকেজ ম্যানেজার এখনো sudoers.d দিয়েই কাজ করে (install.sh সেটা আলাদাভাবে করে)।
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v pkaction >/dev/null 2>&1; then
    echo "❌ polkit এই সিস্টেমে ইনস্টল নেই (pkaction পাওয়া যায়নি)। sudoers.d ব্যবহার করাই সহজ হবে (bash install.sh)।"
    exit 1
fi

TARGET="/etc/polkit-1/rules.d/49-agno-system.rules"
TMP="$(mktemp)"
sed "s#__USER__#$(whoami)#g" "$SCRIPT_DIR/polkit/49-agno-system.rules.template" > "$TMP"
sudo install -m 644 "$TMP" "$TARGET"
rm -f "$TMP"

# পুরনো polkitd JS ইঞ্জিন হলে সার্ভিস রিস্টার্ট লাগে; নতুন ভার্সনে rules.d অটো-রিলোড হয়
sudo systemctl try-restart polkit 2>/dev/null || true

echo "✅ polkit rule বসানো হলো: $TARGET"
echo "   এখন systemctl start/stop/restart/enable/disable পাসওয়ার্ড ছাড়া কাজ করবে (protected ইউনিট বাদে)।"
echo "   টেস্ট করতে: systemctl restart cups  (বা অন্য কোনো নিরাপদ সার্ভিস)"
