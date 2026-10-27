"""Maintenance and monitoring: checks, history, incidents and the monthly health report.

Configuration lives in the project: .yw/monitor.json
{
  "urls": ["https://app.example.com/health"],
  "ssl_hosts": ["app.example.com"],
  "logs_cmd": "ssh deploy@host 'cd /opt/app && docker compose logs --since 65m app'",
  "disk_cmd": "ssh deploy@host df -P /",
  "backup_dir": "/backups" | "backup_cmd": "ssh deploy@host ls -1t /backups",
  "backup_max_age_hours": 26,
  "restore_test_cmd": "ssh deploy@host /opt/app/deploy/restore-test.sh",
  "agent_cmd": "ssh deploy@host cat /var/lib/yw-agent/status.json"
}
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
import ssl
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

ERROR_RX = re.compile(r"(Traceback \(most recent call last\)|\bERROR\b|\bCRITICAL\b|Unhandled|Exception:|"
                      r"\b5\d\d\b.*\b(GET|POST|PUT|DELETE)\b|panic:)")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    value: float | None = None


@dataclass
class Incident:
    id: str
    kind: str
    summary: str
    evidence: str
    first_seen: float
    last_seen: float
    count: int = 1
    status: str = "open"  # open | fixing | fixed | ignored


@dataclass
class MonitorResult:
    time: float
    checks: list[Check] = field(default_factory=list)
    new_incidents: list[Incident] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def text(self) -> str:
        lines = [f"Monitor {datetime.fromtimestamp(self.time).strftime('%Y-%m-%d %H:%M')}: "
                 f"{'ALL OK' if self.ok else 'PROBLEMS'}"]
        lines += [f"  [{'x' if c.ok else ' '}] {c.name}: {c.detail}" for c in self.checks]
        for i in self.new_incidents:
            lines.append(f"\nNEW INCIDENT {i.id} ({i.kind}): {i.summary}\n{i.evidence[:1500]}")
        return "\n".join(lines)


def _sh(cmd: str, timeout: int = 120) -> tuple[int, str]:
    try:
        from ..sandbox.local import shell_args
        args, use_shell = shell_args(cmd)
        r = subprocess.run(args, shell=use_shell, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def check_url(url: str, verify: bool = True) -> Check:
    start = time.monotonic()
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True, verify=verify)
        ms = (time.monotonic() - start) * 1000
        ok = r.status_code < 400 and ms < 5000
        return Check(f"up {url}", ok, f"HTTP {r.status_code}, {ms:.0f} ms" + ("" if ms < 5000 else " (slow)"), ms)
    except httpx.HTTPError as e:
        return Check(f"up {url}", False, f"DOWN: {type(e).__name__}: {e}"[:300])


def ssl_days_left(host: str, port: int = 443, verify: bool = True) -> float:
    ctx = ssl.create_default_context()
    if not verify:  # only for self-signed development certificates
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=10) as sock, ctx.wrap_socket(sock, server_hostname=host) as s:
        cert = s.getpeercert()
        der = s.getpeercert(binary_form=True)
    not_after = cert.get("notAfter") if cert else None
    if not not_after:
        not_after = _not_after_from_der(der)
    end = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    return (end - datetime.now(timezone.utc)).total_seconds() / 86400


def _not_after_from_der(der: bytes) -> str:
    """Unverified certificates are not decoded by getpeercert(); decode the raw certificate instead."""
    try:
        from cryptography import x509
        return x509.load_der_x509_certificate(der).not_valid_after_utc.strftime("%b %d %H:%M:%S %Y GMT")
    except ImportError:
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
            f.write(ssl.DER_cert_to_PEM_cert(der))
            path = f.name
        try:
            return ssl._ssl._test_decode_cert(path)["notAfter"]  # type: ignore[attr-defined]
        finally:
            Path(path).unlink(missing_ok=True)


def check_ssl(host: str, warn_days: int = 14, verify: bool = True) -> Check:
    h, _, p = host.partition(":")
    try:
        days = ssl_days_left(h, int(p or 443), verify)
    except (OSError, ssl.SSLError, ValueError) as e:
        return Check(f"ssl {host}", False, f"cannot check certificate: {e}"[:300])
    return Check(f"ssl {host}", days >= warn_days, f"certificate valid for {days:.0f} more days", days)


def error_signatures(log_text: str) -> dict[str, list[str]]:
    """Group error lines by a normalized signature so the same bug counts once."""
    groups: dict[str, list[str]] = {}
    lines = log_text.splitlines()
    for i, line in enumerate(lines):
        if not ERROR_RX.search(line):
            continue
        context = "\n".join(lines[i:i + 12])
        last_exc = next((ln for ln in lines[i:i + 40] if re.match(r"^\s*\w+(Error|Exception)\b", ln.strip())), line)
        norm = re.sub(r"\d+", "N", re.sub(r"0x[0-9a-f]+|'[^']*'|\"[^\"]*\"", "?", last_exc.strip()))[:200]
        groups.setdefault(norm, []).append(context)
    return groups


class Monitor:
    def __init__(self, root: Path, run=_sh):
        self.root = Path(root)
        self.dir = self.root / ".yw" / "ops"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run = run

    def config(self) -> dict:
        p = self.root / ".yw" / "monitor.json"
        return json.loads(p.read_text("utf-8")) if p.exists() else {}

    def save_config(self, cfg: dict) -> None:
        (self.root / ".yw" / "monitor.json").write_text(json.dumps(cfg, indent=2), "utf-8")

    # ------------------------------------------------------------ incidents
    def incidents(self) -> list[Incident]:
        p = self.dir / "incidents.json"
        return [Incident(**x) for x in json.loads(p.read_text("utf-8"))] if p.exists() else []

    def _save_incidents(self, items: list[Incident]) -> None:
        (self.dir / "incidents.json").write_text(json.dumps([asdict(i) for i in items], indent=2), "utf-8")

    def record(self, kind: str, summary: str, evidence: str) -> Incident | None:
        """Add or update an incident. Returns it when it is NEW."""
        iid = hashlib.sha1(f"{kind}:{summary}".encode()).hexdigest()[:8]
        items = self.incidents()
        now = time.time()
        for i in items:
            if i.id == iid:
                i.last_seen, i.count = now, i.count + 1
                if i.status == "fixed":
                    i.status = "open"  # it came back
                    self._save_incidents(items)
                    return i
                self._save_incidents(items)
                return None
        inc = Incident(iid, kind, summary, evidence, now, now)
        items.append(inc)
        self._save_incidents(items)
        return inc

    def set_status(self, iid: str, status: str) -> Incident:
        items = self.incidents()
        for i in items:
            if i.id == iid:
                i.status = status
                self._save_incidents(items)
                return i
        raise KeyError(iid)

    # ------------------------------------------------------------ checks
    def run_checks(self) -> MonitorResult:
        cfg = self.config()
        res = MonitorResult(time.time())
        verify = not cfg.get("insecure_tls", False)
        for url in cfg.get("urls", []):
            c = check_url(url, verify)
            res.checks.append(c)
            if not c.ok and (inc := self.record("downtime", f"{url} is down or slow", c.detail)):
                res.new_incidents.append(inc)
        for host in cfg.get("ssl_hosts", []):
            c = check_ssl(host, cfg.get("ssl_warn_days", 14), verify)
            res.checks.append(c)
            if not c.ok and (inc := self.record("ssl", f"certificate for {host} needs attention", c.detail)):
                res.new_incidents.append(inc)
        if cfg.get("logs_cmd"):
            code, text = self.run(cfg["logs_cmd"])
            groups = error_signatures(text) if code == 0 else {}
            res.checks.append(Check("error logs", not groups and code == 0,
                                    f"{sum(len(v) for v in groups.values())} error lines, {len(groups)} distinct"
                                    if code == 0 else f"cannot read logs: {text[-200:]}"))
            for sig, samples in groups.items():
                if inc := self.record("error", sig, samples[0]):
                    res.new_incidents.append(inc)
        if cfg.get("disk_cmd"):
            code, text = self.run(cfg["disk_cmd"])
            m = re.findall(r"(\d+)%", text)
            used = max(map(int, m)) if m else None
            res.checks.append(Check("disk", used is not None and used < cfg.get("disk_warn_percent", 85),
                                    f"{used}% used" if used is not None else text[-200:], used))
        if cfg.get("backup_dir") or cfg.get("backup_cmd"):
            res.checks.append(self._check_backups(cfg))
        if cfg.get("restore_test_cmd"):
            code, text = self.run(cfg["restore_test_cmd"])
            c = Check("backup restores", code == 0, "restore test passed" if code == 0 else text[-300:])
            res.checks.append(c)
            if not c.ok and (inc := self.record("backup", "backup restore test failed", text[-2000:])):
                res.new_incidents.append(inc)
        if cfg.get("agent_cmd"):
            code, text = self.run(cfg["agent_cmd"])
            try:
                agent = json.loads(text)
                bad = [k for k, v in agent.get("checks", {}).items() if not v.get("ok")]
                res.checks.append(Check("server agent", not bad, "all server checks ok" if not bad else
                                        "failing: " + ", ".join(bad)))
            except json.JSONDecodeError:
                res.checks.append(Check("server agent", False, f"no agent status: {text[-200:]}"))
        with (self.dir / "history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": res.time, "checks": [asdict(c) for c in res.checks]}) + "\n")
        return res

    def _check_backups(self, cfg: dict) -> Check:
        max_age = cfg.get("backup_max_age_hours", 26)
        if cfg.get("backup_dir") and Path(cfg["backup_dir"]).is_dir():
            files = sorted(Path(cfg["backup_dir"]).glob("*"), key=lambda p: p.stat().st_mtime)
            if not files:
                return Check("backups fresh", False, "no backups found")
            age = (time.time() - files[-1].stat().st_mtime) / 3600
        else:
            code, text = self.run(cfg.get("backup_cmd", f"ls -1t {cfg.get('backup_dir', '')}"))
            stamps = re.findall(r"(20\d\d)[-_]?(\d\d)[-_]?(\d\d)[T_-]?(\d\d)?(\d\d)?", text)
            if code != 0 or not stamps:
                return Check("backups fresh", False, f"cannot list backups: {text[-200:]}")
            y, mo, d, h, mi = stamps[0]
            newest = datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
        return Check("backups fresh", age <= max_age, f"newest backup is {age:.1f} hours old", age)

    # ------------------------------------------------------------ report
    def health_report(self, days: int = 30) -> str:
        since = time.time() - days * 86400
        rows = []
        p = self.dir / "history.jsonl"
        if p.exists():
            rows = [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
            rows = [r for r in rows if r["time"] >= since]
        up_total = up_ok = 0
        latencies: list[float] = []
        for r in rows:
            for c in r["checks"]:
                if c["name"].startswith("up "):
                    up_total += 1
                    up_ok += c["ok"]
                    if c.get("value"):
                        latencies.append(c["value"])
        incs = [i for i in self.incidents() if i.last_seen >= since]
        lines = [f"# Sağlık raporu / Health report — last {days} days", "",
                 f"- Checks run: {len(rows)}",
                 f"- Uptime: {100 * up_ok / up_total:.2f}%" if up_total else "- Uptime: no URL checks configured",
                 f"- Average response: {sum(latencies) / len(latencies):.0f} ms" if latencies else "- Average response: -",
                 f"- Incidents: {len(incs)} ({sum(i.status == 'fixed' for i in incs)} fixed, "
                 f"{sum(i.status == 'open' for i in incs)} open)"]
        last = rows[-1]["checks"] if rows else []
        for c in last:
            if not c["name"].startswith("up "):
                lines.append(f"- {c['name']}: {'OK' if c['ok'] else 'PROBLEM'} — {c['detail']}")
        if incs:
            lines += ["", "## Incidents"] + [f"- [{i.status}] {i.kind}: {i.summary} (seen {i.count}x)" for i in incs]
        return "\n".join(lines)
