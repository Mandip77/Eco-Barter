# Build Stage
FROM golang:alpine AS builder

WORKDIR /app
COPY go.mod ./

# Temporarily copy go.sum if it exists, or just download without it initially if we mount properly
# To ensure go.sum runs locally, we can just run go mod tidy during build
COPY . .
RUN go mod tidy
RUN go build -o trade-engine .

# Run Stage
FROM alpine:latest

WORKDIR /app
COPY --from=builder /app/trade-engine .

CMD ["./trade-engine"]
