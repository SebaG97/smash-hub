FROM node:22.22.0-alpine AS dependencies
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci
FROM dependencies AS development
COPY apps/web/ ./
EXPOSE 3000
CMD ["npm", "run", "dev"]
FROM dependencies AS build
COPY apps/web/ ./
ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build
FROM node:22.22.0-alpine AS production
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
