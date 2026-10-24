# Builder for custom Debian-based live/installer ISOs (live-build). Run with --privileged.
FROM debian:bookworm
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      live-build debootstrap squashfs-tools xorriso isolinux syslinux-common grub-pc-bin grub-efi-amd64-bin mtools \
      dosfstools ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
