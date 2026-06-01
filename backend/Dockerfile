FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app code explicitly — forces Docker to invalidate cache
COPY main.py .
COPY app/ ./app/

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
# force redeploy Mon Jun  1 19:40:01 UTC 2026
