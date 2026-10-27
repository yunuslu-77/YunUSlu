"""Security Lab tools and the security done gate."""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path

from ...core.errors import ToolError
from ...engine.engine import GateResult
from ...extensions import register, register_gate
from ...tools.registry import EXTERNAL, Tool, obj
from . import dast, scanners
from .scanners import Finding, sort_findings

EXTERNAL_TOOLS = {
    "semgrep": ("semgrep --config auto --json --quiet .", "pip install semgrep"),
    "bandit": ("bandit -r . -f json -q -x ./tests,./node_modules,./.venv", "pip install bandit"),
    "pip-audit": ("pip-audit -f json", "pip install pip-audit"),
    "npm-audit": ("npm audit --json", "comes with npm"),
    "gitleaks": ("gitleaks detect --no-banner --report-format json --report-path /dev/stdout", "gitleaks binary"),
    "trivy": ("trivy fs --quiet --format json .", "trivy binary"),
}


def quick_scan(root: Path, history: bool = False) -> list[Finding]:
    return sort_findings(scanners.scan_secrets(root, history) + scanners.scan_python(root) + scanners.scan_js(root)
                         + scanners.scan_config(root))


def _parse_external(name: str, output: str) -> list[Finding]:
    """Normalize the JSON of external scanners into findings (best effort, keeps the raw count)."""
    out: list[Finding] = []
    start = output.find("{") if output.find("{") != -1 else output.find("[")
    try:
        data = json.loads(output[start:]) if start >= 0 else None
    except json.JSONDecodeError:
        data = None
    if data is None:
        return out
    if name == "semgrep":
        for r in data.get("results", []):
            sev = {"ERROR": "high", "WARNING": "medium"}.get(r.get("extra", {}).get("severity"), "low")
            out.append(Finding(sev, "semgrep:" + r.get("check_id", "?").split(".")[-1], r.get("path", ""),
                               r.get("start", {}).get("line", 0), r.get("extra", {}).get("message", "")[:300],
                               "See the rule's documentation."))
    elif name == "bandit":
        for r in data.get("results", []):
            out.append(Finding(r.get("issue_severity", "low").lower(), "bandit:" + r.get("test_id", ""),
                               r.get("filename", ""), r.get("line_number", 0), r.get("issue_text", ""),
                               r.get("more_info", "")))
    elif name == "pip-audit":
        for dep in data.get("dependencies", []) if isinstance(data, dict) else []:
            for v in dep.get("vulns", []):
                out.append(Finding("high", "dep:" + v.get("id", ""), f"{dep['name']}=={dep.get('version')}", 0,
                                   v.get("description", "")[:200] or "Known vulnerability",
                                   f"Upgrade to {', '.join(v.get('fix_versions', [])) or 'a fixed version'}."))
    elif name == "npm-audit":
        for pkg, v in (data.get("vulnerabilities") or {}).items():
            out.append(Finding({"critical": "critical", "high": "high", "moderate": "medium"}.get(v.get("severity"), "low"),
                               "dep:npm", pkg, 0, f"{pkg} has known vulnerabilities.", "Run npm audit fix or upgrade."))
    elif name == "gitleaks" and isinstance(data, list):
        for r in data:
            out.append(Finding("critical", "gitleaks:" + r.get("RuleID", ""), r.get("File", ""), r.get("StartLine", 0),
                               "Secret detected.", "Remove and rotate it."))
    elif name == "trivy":
        for res in data.get("Results", []):
            for v in res.get("Vulnerabilities") or []:
                out.append(Finding(v.get("Severity", "LOW").lower(), "trivy:" + v.get("VulnerabilityID", ""),
                                   res.get("Target", ""), 0, v.get("Title", "")[:200],
                                   f"Upgrade {v.get('PkgName')} to {v.get('FixedVersion') or 'a fixed version'}."))
    return out


def report(findings: list[Finding], title: str) -> str:
    if not findings:
        return f"{title}: no findings."
    counts = {s: sum(f.severity == s for f in findings) for s in scanners.SEVERITY_ORDER}
    head = f"{title}: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n)
    return head + "\n\n" + "\n\n".join(f.render() for f in findings[:80])


@register
def install(session) -> None:
    reg, root, sb = session.registry, session.workspace.root, session.sandbox

    def security_scan(kind: str = "all", url: str = "", owned: bool = False) -> str:
        findings: list[Finding] = []
        notes: list[str] = []
        if kind in ("all", "secrets"):
            findings += scanners.scan_secrets(root)
        if kind in ("all", "code"):
            findings += scanners.scan_python(root) + scanners.scan_js(root)
        if kind in ("all", "config"):
            findings += scanners.scan_config(root)
        if kind in ("all", "deps", "code", "secrets", "container"):
            wanted = {"deps": ["pip-audit", "npm-audit", "trivy"], "code": ["semgrep", "bandit"],
                      "secrets": ["gitleaks"], "container": ["trivy"]}.get(kind) or list(EXTERNAL_TOOLS)
            for name in wanted:
                cmd, how = EXTERNAL_TOOLS[name]
                exe = cmd.split()[0]
                if name == "npm-audit" and not (root / "package-lock.json").exists():
                    continue
                if name == "pip-audit" and not any((root / f).exists() for f in ("requirements.txt", "pyproject.toml")):
                    continue
                probe = sb.run(f"command -v {exe}", timeout=20)
                if probe.exit_code != 0:
                    notes.append(f"{name} not installed in the sandbox ({how}); skipped.")
                    continue
                r = sb.run(cmd, timeout=900)
                findings += _parse_external(name, r.output)
        if kind == "dast":
            if not url:
                raise ToolError("no_url", "dast needs the URL of your running app.")
            host = urllib.parse.urlparse(url).hostname or ""
            local = host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local")
            if not local and not owned:
                raise ToolError("not_owned", "Dynamic tests only run against your own app.",
                                "For a non-local address set owned=true after the user confirms they own it.")
            findings += dast.scan_url(url)
        findings = sort_findings(findings)
        text = report(findings, f"Security scan ({kind})")
        if kind == "all":  # remembered for the launch checklist and the health report
            counts = {sev: sum(f.severity == sev for f in findings) for sev in scanners.SEVERITY_ORDER}
            (root / ".yw").mkdir(exist_ok=True)
            (root / ".yw" / "security.json").write_text(json.dumps({"time": time.time(), "counts": counts}), "utf-8")
        return text + ("\n\nNotes:\n" + "\n".join(notes) if notes else "")

    def security_setup() -> str:
        r = sb.install("pip", ["semgrep", "bandit", "pip-audit"])
        return r.to_text()

    reg.register(Tool("security_scan", "Security Lab. kind: all, secrets, code, config, deps, container, dast "
                      "(dynamic tests against your running app's URL; local only unless owned=true).",
                      obj({"kind": {"type": "string", "enum": ["all", "secrets", "code", "config", "deps", "container",
                                                               "dast"]},
                           "url": {"type": "string"}, "owned": {"type": "boolean"}}),
                      security_scan, "exec", "security"))
    reg.register(Tool("security_setup", "Install extra scanners (semgrep, bandit, pip-audit) in the sandbox.",
                      obj({}), security_setup, EXTERNAL, "security"))

    def block_unsafe_deploy(tool, args) -> str | None:
        """Runs at call time, so it works whatever order the tools were registered in."""
        if tool.name != "deploy_run":
            return None
        critical = [f for f in quick_scan(root) if f.severity == "critical"]
        if not critical:
            return None
        return ("ERROR [security_block]: Deployment blocked: critical security findings.\n\n"
                + "\n\n".join(f.render() for f in critical[:20]) + "\nHINT: Fix them, then deploy again.")

    reg.before_call.append(block_unsafe_deploy)


@register_gate
def install_gate(session) -> None:
    def gate(engine) -> GateResult:
        crit = [f for f in quick_scan(engine.root) if f.severity in ("critical", "high")]
        return GateResult("no critical or high security findings", not crit,
                          "\n".join(f.render() for f in crit[:15]))
    if session.engine.quality in ("balanced", "max"):
        session.engine.extra_gates.append(gate)
