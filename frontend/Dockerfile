# Quorum frontend — Next.js 14 + React + d3-force + framer-motion
#
# Multi-stage build:
#   1. deps    — install npm packages with a clean cache layer
#   2. builder — build the production Next.js bundle
#   3. runner  — minimal runtime image with just the build output
#
# Build:
#   docker build -f frontend/Dockerfile -t quorum-frontend ./frontend
# (docker-compose.yml uses context: ./frontend for this.)

# ============================================
# Stage 1 — install dependencies
# ============================================
FROM node:20-alpine AS deps
WORKDIR /app

# Install OS packages needed by some npm modules at install time
RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json* ./
RUN npm ci

# ============================================
# Stage 2 — build the production bundle
# ============================================
FROM node:20-alpine AS builder
WORKDIR /app

# Pull node_modules from the deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable Next telemetry during the build
ENV NEXT_TELEMETRY_DISABLED=1

# The API base URL must be baked in at build time because Next.js inlines
# NEXT_PUBLIC_* env vars during compilation. Override at build time with
# --build-arg if needed.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN npm run build

# ============================================
# Stage 3 — minimal runtime
# ============================================
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Run as a non-root user
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Copy only what the runtime needs
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
