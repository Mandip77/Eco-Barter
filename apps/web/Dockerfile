FROM node:20-alpine AS builder

WORKDIR /app

# Copy package.json
COPY apps/web/package.json ./

# Install dependencies using legacy-peer-deps to resolve Svelte/Vite version conflicts
RUN npm install --legacy-peer-deps

# Copy the rest of the web app source
COPY apps/web/ .

# Set build-time environment variables for SvelteKit/Vite
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build the application
RUN npm run build

# ---

FROM node:20-alpine

WORKDIR /app
COPY --from=builder /app/build build/
COPY --from=builder /app/package.json .
COPY --from=builder /app/node_modules node_modules/

ENV PORT=3000
ENV NODE_ENV=production
EXPOSE 3000

CMD ["node", "build/index.js"]
