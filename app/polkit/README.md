# polkit — sudoers-এর বিকল্প (systemd সার্ভিস কন্ট্রোলের জন্য)

`install.sh` ডিফল্টভাবে `/etc/sudoers.d/agno-system` দিয়ে নির্দিষ্ট বাইনারিতে
পাসওয়ার্ডহীন sudo সেট করে। কিছু পরিবেশে (বিশেষত যেখানে sudoers এডিট করা নীতিগতভাবে
এড়ানো হয়, বা polkit-centric ডিস্ট্রো যেমন Fedora Workstation) **polkit rule**
বিকল্প হিসেবে ব্যবহার করা যায় — শুধু `systemctl` অ্যাকশনের জন্য (প্যাকেজ ম্যানেজার
এখনো sudoers-নির্ভর, কারণ apt/dnf/pacman-এর কোনো স্ট্যান্ডার্ড polkit action-id নেই)।

## ব্যবহার
```bash
bash scripts/install_polkit.sh
```
এটা `49-agno-system.rules.template`-এ `__USER__` প্রতিস্থাপন করে
`/etc/polkit-1/rules.d/49-agno-system.rules`-এ বসায়।

## sudoers vs polkit — কোনটা কখন
| | sudoers.d | polkit rule |
|---|---|---|
| কভার করে | প্যাকেজ ম্যানেজার + systemctl | শুধু systemctl (এই zip-এ) |
| মডেল | ক্লাসিক Unix sudo | ডেস্কটপ-native (session/D-Bus সচেতন) |
| GUI প্রম্পট সাপোর্ট | না | চাইলে rule বদলে auth_self/GUI prompt করা যায় |
| সেটআপ | install.sh-এর অংশ | আলাদা ঐচ্ছিক স্ক্রিপ্ট |

দুটোই protected ইউনিট (ssh/network/dbus/systemd-core/agno-system নিজে)
হার্ড-ব্লক করে রাখে — approval দিলেও bypass হয় না।
