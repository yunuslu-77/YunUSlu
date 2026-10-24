# Builder for microcontrollers: PlatformIO (Arduino, ESP32, STM32, RP2040) and arduino-cli.
FROM python:3.12-slim
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl git ca-certificates && \
    pip install --no-cache-dir platformio && \
    curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=/usr/local/bin sh && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /src
