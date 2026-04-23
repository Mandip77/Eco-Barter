# Build stage — vulnerabilities here don't reach the runtime image (multi-stage build)
FROM golang:1.25-alpine AS builder

# Patch all Alpine packages so the builder layer passes security scans
RUN apk upgrade --no-cache

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
# Disable CGO, strip debug info, build a fully static binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o trade-engine .

# Runtime stage — minimal scratch-like image
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app
COPY --from=builder /app/trade-engine .

USER nonroot:nonroot

CMD ["/app/trade-engine"]
