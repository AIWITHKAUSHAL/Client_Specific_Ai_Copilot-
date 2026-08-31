# ---------------------------------------------------------------------------
# Logistics Operations Copilot
#
# Builds a container that serves the FastAPI production interface.
# The CLI prototype is available in the same image:
#     docker run -it --rm fde-logistics-copilot python app.py
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COPILOT_ENV=docker

WORKDIR /app

# Dependencies first so code changes do not invalidate the layer cache.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user (least privilege - see docs/security.md).
RUN useradd --create-home --uid 1000 copilot \
    && mkdir -p /app/logs \
    && chown -R copilot:copilot /app
USER copilot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
