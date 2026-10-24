"""Store uploads. Always run on the user's computer with their accounts, and always ask first."""

from __future__ import annotations

STORES = {
    "google-play": {"title": "Google Play", "command": "fastlane supply --aab {artifact} --track {track} "
                    "--json_key {json_key} --package_name {package}",
                    "needs": ["Google Play developer account", "service account JSON key (json_key)", "fastlane"]},
    "app-store": {"title": "App Store (TestFlight)", "command": "xcrun altool --upload-app -f {artifact} -t ios "
                  "--apiKey {api_key} --apiIssuer {issuer}",
                  "needs": ["A Mac with Xcode", "Apple Developer account", "App Store Connect API key"]},
    "microsoft-store": {"title": "Microsoft Store", "command": "msstore publish {artifact}",
                        "needs": ["Microsoft Partner Center account", "msstore CLI"]},
    "snap-store": {"title": "Snap Store", "command": "snapcraft upload --release={track} {artifact}",
                   "needs": ["snapcraft login"]},
    "flathub": {"title": "Flathub", "command": "",
                "needs": ["Open a pull request to github.com/flathub with your manifest (reviewed by Flathub)"]},
    "chrome-web-store": {"title": "Chrome Web Store", "command": "npx --yes chrome-webstore-upload-cli upload "
                         "--source {artifact} --extension-id {extension_id}",
                         "needs": ["Chrome Web Store developer account (one-time fee)", "API client id/secret/refresh token"]},
    "firefox-addons": {"title": "Firefox Add-ons", "command": "npx --yes web-ext sign --channel listed "
                       "--api-key {api_key} --api-secret {api_secret}", "needs": ["addons.mozilla.org API key"]},
    "pypi": {"title": "PyPI", "command": "python -m twine upload {artifact}", "needs": ["PyPI token (TWINE_PASSWORD)"]},
    "npm": {"title": "npm", "command": "npm publish {artifact}", "needs": ["npm login"]},
    "docker-hub": {"title": "Docker Hub / GHCR", "command": "docker push {image}", "needs": ["docker login"]},
    "github-releases": {"title": "GitHub Releases", "command": "gh release create {tag} {artifact} --generate-notes",
                        "needs": ["GitHub CLI logged in"]},
}


def upload_command(store: str, **fields) -> str:
    info = STORES[store]
    if not info["command"]:
        return ""
    return info["command"].format(**fields)
