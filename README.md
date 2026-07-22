# Noor Agent — পোর্টেবল ভার্সন (Windows / Linux / macOS)

Noor OS ইনস্টল না করেও যেকোনো মেশিনে **এক কমান্ডে** পুরো Agno এজেন্ট সিস্টেম (১৭টা টিম)
চালানোর জন্য এই পোর্টেবল ভার্সন। শুধু **Docker** ইনস্টল থাকতে হবে।

## যা লাগবে
- Docker Desktop (Windows/macOS) অথবা Docker Engine + Compose (Linux)
  ইনস্টল গাইড: https://docs.docker.com/get-docker/
- ইন্টারনেট কানেকশন (মডেল কল + প্রথমবার ইমেজ বিল্ড)

## চালানো (এক কমান্ড)
**Linux / macOS:**
```bash
bash start.sh
```
**Windows:** `start.bat` ফাইলে ডাবল-ক্লিক করুন (অথবা PowerShell-এ `docker compose up -d --build`)।

প্রথমবার কয়েক মিনিট লাগবে (ইমেজ বিল্ড হয়)। এরপর ব্রাউজারে খুলুন:

> http://localhost:8000  
> ইউজারনেম: `agno`  পাসওয়ার্ড: `noor12345`

লগ দেখতে: `docker compose logs -f agno`  ·  বন্ধ করতে: `docker compose down`

## API key
`.env` ফাইলে আপনার OpenRouter key আগে থেকেই বসানো আছে। বদলাতে চাইলে `.env`-এর
`OPENROUTER_API_KEY=` লাইনটা এডিট করে `docker compose restart agno` দিন।

## অটো-আপডেট (GitHub থেকে)
নতুন কোড এলে আপডেট করতে:
```bash
bash update.sh
```
আপনার নিজের GitHub রিপো ব্যবহার করলে `.env`-এ সেট করুন —
```
AUTO_UPDATE=1
NOOR_REPO_URL=https://github.com/<আপনার-ইউজার>/<রিপো>.git
```
তাহলে কন্টেইনার প্রতিবার চালু হওয়ার সময় সর্বশেষ কোড টেনে নেবে।

## কী কাজ করে, কী করে না
- ✅ চ্যাট, রিসার্চ, কোডিং, সোশ্যাল, ই-কমার্স, নোটিফিকেশন, শিডিউলার সহ ১৭টা টিম।
- ⚠️ ভয়েস (মাইক), স্ক্রিন-রিডিং/ডেস্কটপ-কন্ট্রোল ফিচার কন্টেইনারে চলে না (হার্ডওয়্যার/GUI লাগে)
  — এগুলোর জন্য পূর্ণ **Noor OS** ভার্সন ব্যবহার করুন।
