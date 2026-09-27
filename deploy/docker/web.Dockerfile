# syntax=docker/dockerfile:1.7
# Web UI: static build served by Caddy, /api reverse-proxied to the API service (SSE-safe).
FROM node:24-trixie-slim AS build
RUN npm install -g --silent pnpm@12.6.0
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/contracts-ts packages/contracts-ts
COPY web web
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile && pnpm --dir web exec vite build

FROM caddy:2.11-alpine
ARG FAL_SOURCE_REVISION=unknown
COPY deploy/docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/web/dist /srv
COPY LICENSE NOTICE /usr/share/doc/formal-agent-lab/
LABEL org.opencontainers.image.source="https://github.com/3351666087/formal-agent-lab" \
      org.opencontainers.image.revision="${FAL_SOURCE_REVISION}" \
      org.opencontainers.image.licenses="Apache-2.0"
EXPOSE 8080
