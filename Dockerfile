FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/agno_system

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

# ডিপেন্ডেন্সি আগে (লেয়ার-ক্যাশ — কোড বদলালে আবার সব ইনস্টল হবে না)
COPY app/requirements-portable.txt ./requirements-portable.txt
RUN pip install --upgrade pip && pip install -r requirements-portable.txt

# অ্যাপ কোড
COPY app/ ./

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
