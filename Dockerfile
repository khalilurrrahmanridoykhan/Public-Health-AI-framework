FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /tmp/phframe
RUN pip install --no-cache-dir "/tmp/phframe[postgres]" && rm -rf /tmp/phframe
COPY phframe.yaml /app/phframe.yaml
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready')"
CMD ["phframe", "serve", "--host", "0.0.0.0", "--port", "8000"]
