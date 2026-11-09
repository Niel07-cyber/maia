# syntax=docker/dockerfile:1

# ---------- Stage 1: build the static site ----------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Empty: the site calls the API on its own address (/api/...), through Caddy.
ENV VITE_API_URL=""
RUN npm run build

# ---------- Stage 2: Caddy serves the site and proxies /api to the backend ----------
FROM caddy:2-alpine
COPY --from=build /app/dist /srv
