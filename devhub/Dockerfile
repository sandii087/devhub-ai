FROM python:3.12-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend ./backend
COPY scripts ./scripts
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home devhub
USER 10001
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/ready', timeout=3)"
CMD ["uvicorn", "devhub.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log", "--no-proxy-headers"]
