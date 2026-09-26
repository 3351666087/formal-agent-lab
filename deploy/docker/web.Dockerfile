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
LABEL org.opencontainers.image.revision="${FAL_SOURCE_REVISION}"
EXPOSE 8080
