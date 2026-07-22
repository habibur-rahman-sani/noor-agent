#!/usr/bin/env bash
# install.sh — Agno System-কে যেকোনো Linux মেশিনে এক কমান্ডে ইনস্টল করা
# ============================================================================
# চালাও:  bash install.sh
#
# ডিজাইন নীতি (যাতে এরর/অর্ধেক-ইনস্টল অবস্থা না হয়):
#   - set -euo pipefail : যেকোনো কমান্ড ব্যর্থ হলে সাথে সাথে থামবে, চুপচাপ
#     এগিয়ে যাবে না
#   - ERR trap          : ঠিক কোন লাইনে ব্যর্থ হলো সেটা স্পষ্ট বলবে
#   - idempotent        : বারবার চালালেও সমস্যা হবে না (আগে থেকে থাকলে স্কিপ)
#   - প্রতিটা sudo/সিস্টেম-বদলানো ধাপের আগে স্পষ্ট ব্যাখ্যা + confirmation
#   - sudoers ফাইল বসানোর আগে 'visudo -c' দিয়ে সিনট্যাক্স যাচাই বাধ্যতামূলক
#     (ভুল sudoers ফাইল পুরো sudo-ই ভেঙে দিতে পারে — তাই এই চেক ছাড়া কখনো বসানো হয় না)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info()  { echo -e "\033[1;34mℹ️  $*\033[0m"; }
ok()    { echo -e "\033[1;32m✅ $*\033[0m"; }
warn()  { echo -e "\033[1;33m⚠️  $*\033[0m"; }
fail()  { echo -e "\033[1;31m❌ $*\033[0m"; exit 1; }

trap 'fail "ইনস্টলার লাইন ${LINENO}-এ ব্যর্থ হয়েছে — উপরের এরর মেসেজটা দেখো, ঠিক করে আবার \"bash install.sh\" চালাও।"' ERR

ask_yn() {
    # ask_yn "প্রশ্ন" "Y" -> ডিফল্ট Yes ; ask_yn "প্রশ্ন" "N" -> ডিফল্ট No
    local prompt="$1" default="${2:-Y}" ans
    if [ "$default" = "Y" ]; then
        read -rp "$(info "$prompt [Y/n] ")" ans; ans="${ans:-Y}"
    else
        read -rp "$(info "$prompt [y/N] ")" ans; ans="${ans:-N}"
    fi
    [[ "$ans" =~ ^[Yy]$ ]]
}

echo "════════════════════════════════════════════════════════════"
echo "  Agno System — Linux ইনস্টলার"
echo "════════════════════════════════════════════════════════════"

# ---------------------------------------------------------- 1. distro ---
detect_pm() {
    local ids=""
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        ids="${ID:-} ${ID_LIKE:-}"
    fi
    case " $ids " in
        *debian*|*ubuntu*) echo apt ;;
        *fedora*|*rhel*)   echo dnf ;;
        *arch*)            echo pacman ;;
        *suse*)            echo zypper ;;
        *alpine*)          echo apk ;;
        *)
            if command -v apt-get  >/dev/null 2>&1; then echo apt
            elif command -v dnf    >/dev/null 2>&1; then echo dnf
            elif command -v pacman >/dev/null 2>&1; then echo pacman
            elif command -v zypper >/dev/null 2>&1; then echo zypper
            elif command -v apk    >/dev/null 2>&1; then echo apk
            else echo unknown
            fi
            ;;
    esac
}

PM="$(detect_pm)"
[ "$PM" = "unknown" ] && fail "সাপোর্টেড প্যাকেজ ম্যানেজার (apt/dnf/pacman/zypper/apk) পাওয়া যায়নি। ম্যানুয়ালি সেটআপ করতে হবে।"
ok "ডিটেক্ট করা প্যাকেজ ম্যানেজার: $PM"

[ "$(id -u)" -eq 0 ] && warn "root হিসেবে চালানো হচ্ছে — সাধারণ ইউজার হিসেবে চালানোই ভালো (স্ক্রিপ্ট নিজেই দরকারমতো sudo চাইবে)।"

# ---------------------------------------------- 2. সিস্টেম ডিপেন্ডেন্সি ---
if ask_yn "python3-venv, ffmpeg, tesseract-ocr, xdotool/wmctrl/xclip (ডেস্কটপ কন্ট্রোল), libportaudio2 (ভয়েস) ইনস্টল করা হবে (sudo লাগবে) — এগিয়ে যাবো?"; then
    case "$PM" in
        apt)    sudo apt-get update -y
                sudo apt-get install -y python3-venv python3-pip ffmpeg tesseract-ocr tesseract-ocr-ben \
                    xdotool wmctrl xclip libnotify-bin portaudio19-dev libportaudio2 ;;
        dnf)    sudo dnf install -y python3-virtualenv python3-pip ffmpeg tesseract \
                    xdotool wmctrl xclip libnotify portaudio ;;
        pacman) sudo pacman -Sy --noconfirm python-virtualenv python-pip ffmpeg tesseract \
                    xdotool wmctrl xclip libnotify portaudio ;;
        zypper) sudo zypper --non-interactive install python3-virtualenv python3-pip ffmpeg tesseract-ocr \
                    xdotool wmctrl xclip libnotify-tools portaudio ;;
        apk)    sudo apk add py3-virtualenv py3-pip ffmpeg tesseract-ocr \
                    xdotool wmctrl xclip libnotify portaudio ;;
    esac
    ok "সিস্টেম ডিপেন্ডেন্সি ইনস্টল হলো।"
else
    warn "স্কিপ করা হলো — voice/vision/desktop-control ফিচার এগুলো ছাড়া কাজ নাও করতে পারে, পরে ম্যানুয়ালি ইনস্টল করা যাবে।"
fi

# -------------------------------------------------- 3. Python venv ---
if [ ! -d venv ]; then
    info "venv তৈরি হচ্ছে..."
    python3 -m venv venv
    ok "venv তৈরি হলো।"
else
    info "venv আগে থেকেই আছে, তৈরি করা স্কিপ করা হলো।"
fi

info "Python dependencies ইনস্টল হচ্ছে (কিছুটা সময় লাগতে পারে)..."
./venv/bin/pip install --upgrade pip --quiet
./venv/bin/pip install -r requirements.txt
ok "Python dependencies ইনস্টল হলো।"

# ---------------------------------------------------------- 4. .env ---
if [ ! -f .env ]; then
    cp .env.example .env
    ok ".env তৈরি হলো (.env.example থেকে) — এখন এতে OPENROUTER_API_KEY বসাও।"
else
    info ".env আগে থেকেই আছে, ওভাররাইট করা হলো না।"
fi

# ------------------------------------------------------- 5. MongoDB ---
if command -v docker >/dev/null 2>&1; then
    if [ -n "$(docker ps -aq -f name=^agno-mongo$ 2>/dev/null || true)" ]; then
        info "agno-mongo কন্টেইনার আগে থেকেই আছে, চালু করা হচ্ছে..."
        docker start agno-mongo >/dev/null 2>&1 || true
        ok "MongoDB (agno-mongo) চালু।"
    else
        if ask_yn "Docker দিয়ে MongoDB কন্টেইনার চালু করবো?"; then
            docker run -d --name agno-mongo --restart unless-stopped -p 27017:27017 mongo
            ok "MongoDB কন্টেইনার চালু হলো (agno-mongo)।"
        else
            warn "স্কিপ করা হলো — .env-এ MONGODB_URI ম্যানুয়ালি বসাতে হবে।"
        fi
    fi
else
    warn "Docker পাওয়া যায়নি — MongoDB নিজে থেকে সেটআপ করা হলো না।"
    warn "Docker ইনস্টল করে আবার চালাও, অথবা ম্যানুয়ালি MongoDB বসিয়ে .env-এ MONGODB_URI দাও।"
fi

# --------------------------------------------------------- 6. sudoers ---
setup_sudoers() {
    local user pm_binary systemctl_binary tmp_file
    user="$(whoami)"

    case "$PM" in
        apt)    pm_binary="$(command -v apt-get)" ;;
        dnf)    pm_binary="$(command -v dnf)" ;;
        pacman) pm_binary="$(command -v pacman)" ;;
        zypper) pm_binary="$(command -v zypper)" ;;
        apk)    pm_binary="$(command -v apk)" ;;
    esac
    systemctl_binary="$(command -v systemctl)"

    if [ -z "${pm_binary:-}" ] || [ -z "${systemctl_binary:-}" ]; then
        warn "প্যাকেজ-ম্যানেজার বা systemctl বাইনারির পাথ খুঁজে পাওয়া যায়নি — sudoers সেটআপ স্কিপ করা হলো।"
        return
    fi

    tmp_file="$(mktemp)"
    cat > "$tmp_file" <<SUDOEOF
# Agno System — install.sh জেনারেট করেছে, ইউজারের স্পষ্ট সম্মতি নিয়ে।
# শুধু এই একটা প্যাকেজ-ম্যানেজার বাইনারি আর systemctl-এর নির্দিষ্ট অ্যাকশনের
# জন্য পাসওয়ার্ডহীন sudo — "ALL=(ALL) NOPASSWD: ALL"-এর মতো কিছু না।
$user ALL=(root) NOPASSWD: $pm_binary
$user ALL=(root) NOPASSWD: $systemctl_binary start *
$user ALL=(root) NOPASSWD: $systemctl_binary stop *
$user ALL=(root) NOPASSWD: $systemctl_binary restart *
$user ALL=(root) NOPASSWD: $systemctl_binary enable *
$user ALL=(root) NOPASSWD: $systemctl_binary disable *
SUDOEOF

    # সিনট্যাক্স-যাচাই বাধ্যতামূলক — ভুল হলে কিছুই বসানো হবে না
    if sudo visudo -c -f "$tmp_file" >/dev/null 2>&1; then
        sudo install -m 440 "$tmp_file" /etc/sudoers.d/agno-system
        ok "sudoers.d এন্ট্রি বসানো হলো (/etc/sudoers.d/agno-system) — শুধু '$pm_binary' আর "
        ok "'$systemctl_binary'-এর নির্দিষ্ট অ্যাকশনের জন্য পাসওয়ার্ডহীন sudo।"
    else
        warn "sudoers সিনট্যাক্স যাচাই ব্যর্থ — নিরাপত্তার জন্য কিছুই বসানো হলো না।"
    fi
    rm -f "$tmp_file"
}

echo
warn "এখন Linux System Agent-কে প্যাকেজ ইনস্টল/রিমুভ আর systemctl start/stop/restart/enable/disable"
warn "পাসওয়ার্ড ছাড়া চালানোর অনুমতি (sudoers.d) দেওয়া যাবে। এটা শুধু নির্দিষ্ট দুইটা বাইনারির জন্য —"
warn "'ALL=(ALL) NOPASSWD: ALL'-এর মতো কিছু না। এটার পরেও প্রতিটা অ্যাকশনে UI-তে আলাদা approval লাগবে।"
warn "(বিকল্প: sudoers-এর বদলে শুধু systemd সার্ভিস কন্ট্রোলের জন্য polkit rule ব্যবহার করতে চাইলে"
warn " sudoers স্কিপ করে পরে 'bash scripts/install_polkit.sh' চালাও — polkit/README.md দ্যাখো।)"
if ask_yn "এগিয়ে যাবো?" "N"; then
    setup_sudoers
else
    warn "স্কিপ করা হলো — Linux System Agent প্যাকেজ/সার্ভিস কন্ট্রোল করতে গেলে প্রতিবার স্পষ্ট এরর দেখাবে "
    warn "(পাসওয়ার্ড ছাড়া sudo সেট নেই), ক্র্যাশ করবে না। পরে চাইলে আবার 'bash install.sh' চালাও।"
fi

# ------------------------------------------------------- 7. systemd ---
if ask_yn "systemd সার্ভিস হিসেবে বসিয়ে বুটে অটো-স্টার্ট চালু করবো?"; then
    UNIT_TMP="$(mktemp)"
    sed \
        -e "s#__WORKDIR__#${SCRIPT_DIR}#g" \
        -e "s#__USER__#$(whoami)#g" \
        deploy/linux/agno-system.service.template > "$UNIT_TMP"
    sudo install -m 644 "$UNIT_TMP" /etc/systemd/system/agno-system.service
    rm -f "$UNIT_TMP"
    sudo systemctl daemon-reload
    sudo systemctl enable --now agno-system
    ok "systemd সার্ভিস চালু হলো।"
    info "স্ট্যাটাস দেখতে:  systemctl status agno-system"
    info "লগ দেখতে:        journalctl -u agno-system -f"
else
    info "সার্ভিস সেটআপ স্কিপ করা হলো। ম্যানুয়ালি চালাতে:"
    info "  ./venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000"
fi

# --------------------------------------------------- 8. voice daemon ---
echo
warn "Voice Daemon (wake-word, 'Hey Agno'-টাইপ সবসময়-শোনা মোড) CPU-ভারী (Whisper মডেল"
warn "ক্রমাগত চলে) এবং মাইক্রোফোন অ্যাক্সেস লাগে — তাই ডিফল্টে বন্ধ থাকে।"
if ask_yn "Voice Daemon systemd সার্ভিস হিসেবে বসাবো?" "N"; then
    VOICE_UNIT_TMP="$(mktemp)"
    sed \
        -e "s#__WORKDIR__#${SCRIPT_DIR}#g" \
        -e "s#__USER__#$(whoami)#g" \
        deploy/linux/agno-voice.service.template > "$VOICE_UNIT_TMP"
    sudo install -m 644 "$VOICE_UNIT_TMP" /etc/systemd/system/agno-voice.service
    rm -f "$VOICE_UNIT_TMP"
    sudo systemctl daemon-reload
    sudo systemctl enable --now agno-voice
    ok "agno-voice সার্ভিস চালু হলো। লগ: journalctl -u agno-voice -f"
    info "wake word বদলাতে .env-এ WAKE_WORDS সেট করে সার্ভিস রিস্টার্ট করো।"
else
    info "স্কিপ করা হলো। পরে ম্যানুয়ালি চালাতে: ./venv/bin/python voice_daemon.py"
fi

echo
echo "════════════════════════════════════════════════════════════"
ok "ইনস্টলেশন শেষ!"
echo "════════════════════════════════════════════════════════════"
info "১. .env ফাইলে OPENROUTER_API_KEY বসাও (আর দরকারমতো অন্য টিমের key)।"
info "২. ব্রাউজারে খোলো: http://localhost:8000  (অবজারভেবিলিটি ড্যাশবোর্ড: http://localhost:8000/dashboard)"
info "৩. systemd সার্ভিস চালু থাকলে সার্ভিস রিস্টার্ট করো:  sudo systemctl restart agno-system"
info "৪. Voice Daemon চালু থাকলে 'Hey Agno' / 'জার্ভিস' বলে টেস্ট করো (journalctl -u agno-voice -f দিয়ে লগ দেখো)।"
