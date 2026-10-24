# yWorkspace standard development image: Python + Node.js + git + build tools.
# Build: docker build -t yworkspace/dev:latest src/yworkspace/sandbox/images/dev
FROM python:3.12-slim

RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      git curl ca-certificates build-essential procps unzip xz-utils sqlite3 \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y -qq --no-install-recommends nodejs \
 && npm install -g pnpm \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest ruff
WORKDIR /workspace
