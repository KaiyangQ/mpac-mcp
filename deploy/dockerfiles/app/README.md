# `deploy/dockerfiles/app/` — Next.js frontend Dockerfile

Builds `mpac-web-app:local` — a two-stage node:20-alpine image. First
stage installs deps + runs `next build`; second stage copies just the
`.next/standalone` output, so the final image is small (~245 MB) and
has no dev dependencies.

`NEXT_PUBLIC_API_URL` must be passed in at **build time** via
`--build-arg` (Next.js inlines public env vars into the JS bundle at
build, not runtime). The compose file reads this from
`/etc/mpac/compose.env`.

Build context must be the repo root.
