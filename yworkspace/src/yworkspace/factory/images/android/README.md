Android and Flutter builds use maintained public images (ghcr.io/cirruslabs/android-sdk, ghcr.io/cirruslabs/flutter).
Emulator-based verification needs hardware virtualization (KVM on Linux, Hypervisor.framework on macOS, WHPX on
Windows); without it, APKs are checked structurally and the user is told to test on a device.
