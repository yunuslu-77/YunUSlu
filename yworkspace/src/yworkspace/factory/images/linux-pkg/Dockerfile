# Builder for Linux packages: deb, rpm (fpm), AppImage, Flatpak.
FROM debian:bookworm
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      ruby ruby-dev build-essential rpm dpkg-dev file desktop-file-utils flatpak-builder wget ca-certificates \
      squashfs-tools && gem install --no-document fpm && rm -rf /var/lib/apt/lists/*
RUN wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage \
      -O /usr/local/bin/appimagetool && chmod +x /usr/local/bin/appimagetool
ENV APPIMAGE_EXTRACT_AND_RUN=1
WORKDIR /src
