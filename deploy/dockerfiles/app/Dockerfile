# MPAC Web App — Next.js frontend image.
#
# Two-stage build: node:20-alpine for deps + `next build`, then
# node:20-alpine for the runtime (uses Next's `standalone` output — no
# node_modules in the final image, just a self-contained server.js).
# Used by deploy/aws-lightsail/docker-compose.yml. Build context must be
# the REPO ROOT so `COPY web-app/app/ …` works.
#
#     # from repo root, typically via compose:
#     docker build -f deploy/dockerfiles/app/Dockerfile \
#         --build-arg NEXT_PUBLIC_API_URL=https://mpac-web.duckdns.org \
#         -t mpac-web-app:local .

# ───────────────────────── Stage 1: build ─────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# `NEXT_PUBLIC_*` env vars must be present at BUILD time — Next inlines
# them into the JS bundle. Override at deploy time via `--build-arg` (see
# docker-compose.yml or the docker build example above).
ARG NEXT_PUBLIC_API_URL=https://mpac-web.duckdns.org
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Install deps (cache layer: copy manifests first).
COPY web-app/app/package.json web-app/app/package-lock.json ./
RUN npm ci --no-audit --no-fund --prefer-offline

# App source.
COPY web-app/app/ ./
RUN npm run build

# ───────────────────────── Stage 2: runtime ───────────────────────
FROM node:20-alpine AS runtime

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Non-root user (Next's Docker example also does this).
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Standalone output: `server.js` at the root + a minimal node_modules the
# build traced as actually-used. Plus we need static assets and /public.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
