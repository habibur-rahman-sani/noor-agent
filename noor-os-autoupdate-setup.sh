#!/usr/bin/env bash
# noor-os-autoupdate-setup.sh — ইনস্টল-করা Noor OS-এ এজেন্ট অ্যাপের অটো-আপডেট চালু করে।
# GitHub রিপো থেকে রোজ একবার সর্বশেষ কোড টেনে /opt/agno_system-এ বসায় ও সার্ভিস রিস্টার্ট করে।
#
# চালাও:  sudo bash noor-os-autoupdate-setup.sh https://github.com/<user>/<repo>.git
set -e

REPO_URL="${1:-}"
if [ "$(id -u)" -ne 0 ]; then echo "❌ sudo দিয়ে চালাও"; exit 1; fi
if [ -z "$REPO_URL" ]; then
  echo "ব্যবহার: sudo bash noor-os-autoupdate-setup.sh <GitHub-repo-URL>"; exit 1
fi

# রিপো URL সেভ করি
echo "$REPO_URL" > /etc/noor-repo-url

# আপডেট স্ক্রিপ্ট (clone + copy app/ — /opt/agno_system-এর ফ্ল্যাট লেআউটে ঠিকভাবে বসে)
cat > /usr/local/bin/noor-selfupdate.sh <<'EOF'
#!/usr/bin/env bash
set -e
APP=/opt/agno_system
REPO="$(cat /etc/noor-repo-url 2>/dev/null || true)"
[ -n "$REPO" ] || { echo "রিপো URL সেট নেই"; exit 0; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 "$REPO" "$TMP" >/dev/null 2>&1 || { echo "clone ব্যর্থ"; exit 0; }

NEW="$(git -C "$TMP" rev-parse HEAD)"
OLD="$(cat /var/lib/noor-agent-rev 2>/dev/null || true)"
[ "$NEW" = "$OLD" ] && exit 0   # নতুন কিছু নেই

SRC="$TMP"; [ -d "$TMP/app" ] && SRC="$TMP/app"
cp -rf "$SRC"/. "$APP"/
chown -R agno:agno "$APP" 2>/dev/null || true
[ -x "$APP/venv/bin/pip" ] && "$APP/venv/bin/pip" install -q -r "$APP/requirements.txt" 2>/dev/null || true
systemctl restart agno-system
echo "$NEW" > /var/lib/noor-agent-rev
logger "noor-selfupdate: এজেন্ট আপডেট হলো ($NEW)"
EOF
chmod +x /usr/local/bin/noor-selfupdate.sh

# systemd timer (দিনে একবার) + boot-এ একবার
cat > /etc/systemd/system/noor-selfupdate.service <<'EOF'
[Unit]
Description=Noor Agent self-update from GitHub
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/noor-selfupdate.sh
EOF

cat > /etc/systemd/system/noor-selfupdate.timer <<'EOF'
[Unit]
Description=Run Noor Agent self-update daily
[Timer]
OnBootSec=2min
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now noor-selfupdate.timer
echo "✅ অটো-আপডেট চালু! GitHub-এ পুশ করলে রোজ একবার (এবং প্রতি বুটে) নিজে থেকে আপডেট হবে।"
echo "   এখনই আপডেট করতে:  sudo /usr/local/bin/noor-selfupdate.sh"
