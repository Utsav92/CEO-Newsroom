FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.lock.txt backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY backend/ backend/
COPY --from=frontend /build/dist frontend/dist
RUN groupadd --gid 10001 newsroom && useradd --uid 10001 --gid newsroom --home-dir /app newsroom && mkdir -p /app/data && chown -R newsroom:newsroom /app
USER newsroom
EXPOSE 8788
CMD ["python","-m","uvicorn","app.main:app","--app-dir","backend","--host","0.0.0.0","--port","8788","--no-server-header","--limit-concurrency","64","--timeout-keep-alive","5"]
