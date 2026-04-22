FROM python:3.11-slim

WORKDIR /app

# Install deps as root, then drop privileges
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    addgroup --system appgroup && adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

COPY --chown=appuser:appgroup . .

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
