FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/octop-router
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home router
COPY router ./router
USER 10001:10001
EXPOSE 9080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9080/healthz', timeout=3)" || exit 1
CMD ["uvicorn", "router.app:app", "--host", "0.0.0.0", "--port", "9080", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
