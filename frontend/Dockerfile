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

ARG VITE_API_URL=/api/v1
ARG VITE_KEYCLOAK_URL=/auth
ARG VITE_KEYCLOAK_REALM=app
ARG VITE_KEYCLOAK_CLIENT_ID=app-frontend
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL
ENV VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM
ENV VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID

COPY . .
RUN npm run build

# ── Production (nginx serves static build) ────────────────────────────────────
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
