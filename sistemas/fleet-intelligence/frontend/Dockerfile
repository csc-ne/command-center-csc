# ---------- Build stage ----------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

# Build with the API pointed at the same origin (/api) — nginx proxies.
ENV VITE_API_URL=/api
RUN npm run build

# ---------- Serve stage ----------
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
