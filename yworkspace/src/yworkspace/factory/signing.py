"""Signing manager. Keys live OUTSIDE the project (~/.yworkspace/signing/<project>/), passwords in the secret
store. Tools only ever return names and fingerprints - never key material or passwords - to the model."""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
from pathlib import Path

from ..config import get_secret, home, set_secret


def store_dir(project: str) -> Path:
    d = home() / "signing" / project
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_keys(project: str) -> list[dict]:
    f = store_dir(project) / "keys.json"
    return json.loads(f.read_text("utf-8")) if f.exists() else []


def _save(project: str, items: list[dict]) -> None:
    (store_dir(project) / "keys.json").write_text(json.dumps(items, indent=2), "utf-8")


def create_android_keystore(project: str, alias: str = "upload", dname: str = "CN=YunUSlu, O=YunUSlu, C=TR",
                            validity_days: int = 10000) -> dict:
    if not shutil.which("keytool"):
        raise RuntimeError("keytool (from a JDK) is needed to create an Android keystore.")
    path = store_dir(project) / f"{alias}.jks"
    if path.exists():
        raise RuntimeError(f"A keystore for {alias} already exists; never replace it (updates would be impossible).")
    password = secrets.token_urlsafe(24)
    subprocess.run(["keytool", "-genkeypair", "-v", "-keystore", str(path), "-alias", alias, "-keyalg", "RSA",
                    "-keysize", "4096", "-validity", str(validity_days), "-storepass", password, "-keypass", password,
                    "-dname", dname], check=True, capture_output=True)
    secret_name = f"YW_SIGN_{project.upper().replace('-', '_')}_{alias.upper()}_PASSWORD"
    set_secret(secret_name, password)
    out = subprocess.run(["keytool", "-list", "-v", "-keystore", str(path), "-storepass", password, "-alias", alias],
                         capture_output=True, text=True).stdout
    fp = next((ln.split(":", 1)[1].strip() for ln in out.splitlines() if "SHA256:" in ln), "")
    entry = {"type": "android-keystore", "alias": alias, "file": str(path), "password_secret": secret_name,
             "sha256": fp}
    items = [k for k in list_keys(project) if k["alias"] != alias] + [entry]
    _save(project, items)
    return {k: v for k, v in entry.items() if k != "password_secret"}


def gradle_signing_env(project: str, alias: str = "upload") -> dict[str, str]:
    """Environment variables for a Gradle release build; injected into the builder, never shown to the model."""
    entry = next((k for k in list_keys(project) if k["alias"] == alias), None)
    if entry is None:
        return {}
    pw = get_secret(entry["password_secret"]) or ""
    return {"YW_KEYSTORE": "/signing/" + Path(entry["file"]).name, "YW_KEYSTORE_PASSWORD": pw,
            "YW_KEY_ALIAS": alias, "YW_KEY_PASSWORD": pw}


BACKUP_WARNING = ("Back up the signing folder somewhere safe (it is not in the project). If an Android upload "
                  "key is lost, you must go through Google Play's key reset; with app signing disabled, the app can "
                  "never be updated again.")
