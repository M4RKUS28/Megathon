FROM node:22-alpine AS base

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ── Development (Vite dev server with HMR) ───────────────────────────────────
FROM base AS development

COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ── Build ─────────────────────────────────────────────────────────────────────
FROM base AS builder

COPY . .
RUN npm run build

# ── Production (nginx serves static build) ────────────────────────────────────
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
