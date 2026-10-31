FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    git \
    bubblewrap \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global @openai/codex@0.147.0

WORKDIR /workspace

ENTRYPOINT ["codex"]