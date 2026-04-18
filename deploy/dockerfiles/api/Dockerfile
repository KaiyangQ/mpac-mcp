# MPAC Web App — FastAPI backend image.
#
# Builds a Python 3.12 image running uvicorn on port 8001. Used by
# deploy/aws-lightsail/docker-compose.yml. Build context must be the
# REPO ROOT so the image can COPY web-app/api/ and web-app/api/requirements.txt.
#
#     # from repo root, typically via compose:
#     docker build -f deploy/dockerfiles/api/Dockerfile -t mpac-web-api:local .

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

# SQLite volume mountpoint. On Lightsail this is bind-mounted from
# /var/mpac/data on the host (see docker-compose.yml).
RUN mkdir -p /data

EXPOSE 8001

# Production server — single worker keeps the in-process MPAC coordinator's
# session state consistent (it lives in module globals via mpac_bridge.registry).
# When we outgrow one worker we'll need to externalize the coordinator state.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
