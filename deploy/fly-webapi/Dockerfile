# MPAC Web App — FastAPI backend for fly.io (mpac-web-api).
#
# Build from the REPO ROOT so the context includes web-app/:
#
#     fly deploy --config deploy/fly-webapi/fly.toml \
#                --dockerfile deploy/fly-webapi/Dockerfile

FROM python:3.12-slim

# System deps — cryptography needs build tools on ARM wheels; on x86_64 the
# wheel is prebuilt. Keep the image slim by cleaning apt lists.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache-friendly layer).
COPY web-app/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY web-app/api/ ./api/

# Volume mountpoint (fly volume `webapi_data` is mounted here via fly.toml).
RUN mkdir -p /data

EXPOSE 8001

# Production server — single worker keeps the in-process MPAC coordinator's
# session state consistent (it lives in module globals via mpac_bridge.registry).
# When we outgrow one worker we'll need to externalize the coordinator state.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
