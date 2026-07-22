// sw.js — খুবই বেসিক অফলাইন cache (শুধু app-shell: index.html + manifest + icon)।
// চ্যাট/API রিকোয়েস্ট (ইন্টারনেট/লোকাল-সার্ভার লাগবেই) ক্যাশ করা হয় না ইচ্ছাকৃতভাবে,
// যাতে পুরনো ক্যাশড রেসপন্স ইউজারকে বিভ্রান্ত না করে।
const CACHE_NAME = "agno-shell-v1";
const SHELL_FILES = ["/", "/static/manifest.json", "/static/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // শুধু app-shell স্ট্যাটিক ফাইলের জন্য cache-first; বাকি সব (API/WS) নেটওয়ার্কেই যাবে
  if (event.request.method === "GET" && SHELL_FILES.includes(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
