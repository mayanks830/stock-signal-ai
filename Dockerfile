# ── Build frontend ────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Python app ────────────────────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# Install system deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends gcc libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy built frontend from build stage
COPY --from=frontend /app/frontend/dist /app/frontend/dist

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py"]
