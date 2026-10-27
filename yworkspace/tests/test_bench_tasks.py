"""Every Bench task must be solvable: a reference solution passes its hidden tests, the starting files fail."""
import pytest

from yworkspace.bench import runner as br
from yworkspace.bench import tasks as bt

REFERENCE = {
    "fix-average": {"stats.py": "def average(values):\n    if not values:\n        raise ValueError('empty')\n"
                                "    return sum(values) / len(values)\n\n\ndef spread(values):\n"
                                "    return max(values) - min(values)\n"},
    "slug-unicode": {"text_utils.py": "import re\n\nTR = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')\n\n\n"
                                      "def slugify(title):\n    s = title.translate(TR).lower()\n"
                                      "    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')\n"},
    "todo-feature": {"todo.py": "import itertools\nimport json\n\n_ids = itertools.count(1)\n\n\ndef new_store():\n"
                                "    return {}\n\n\ndef add(store, title):\n    item_id = next(_ids)\n"
                                "    store[item_id] = {'id': item_id, 'title': title, 'done': False}\n"
                                "    return item_id\n\n\ndef complete(store, item_id):\n    store[item_id]['done'] = True\n\n\n"
                                "def pending(store):\n    return [i for i in sorted(store.values(), key=lambda i: i['id']) "
                                "if not i['done']]\n\n\ndef save(store, path):\n    with open(path, 'w', encoding='utf-8') "
                                "as f:\n        json.dump(list(store.values()), f, ensure_ascii=False)\n\n\n"
                                "def load(path):\n    with open(path, encoding='utf-8') as f:\n"
                                "        return {i['id']: i for i in json.load(f)}\n"},
    "wordcount-cli": {"wc.py": "import re\nimport sys\nfrom collections import Counter\n\n\ndef main():\n"
                               "    if len(sys.argv) != 2:\n        print('usage: python wc.py FILE', file=sys.stderr)\n"
                               "        return 2\n    try:\n        text = open(sys.argv[1], encoding='utf-8').read()\n"
                               "    except OSError as e:\n        print(f'cannot read {sys.argv[1]}: {e}', file=sys.stderr)\n"
                               "        return 1\n    words = re.findall(r'[^\\W\\d_]+', text.replace('İ', 'i').replace('I', 'ı').lower())\n"
                               "    c = Counter(words)\n    top = min(c.items(), key=lambda kv: (-kv[1], kv[0])) if c else ('-', 0)\n"
                               "    print(f'lines {len(text.splitlines())}')\n    print(f'words {len(words)}')\n"
                               "    print(f'top {top[0]} {top[1]}')\n    return 0\n\n\n"
                               "if __name__ == '__main__':\n    sys.exit(main())\n"},
    "shortener-service": {"shortener.py": '''import json
import os
import secrets
import string
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DATA = Path(os.environ.get("SHORTENER_DATA", Path(__file__).with_name("links.json")))
ALPHABET = string.ascii_letters + string.digits


def _load():
    return json.loads(DATA.read_text("utf-8")) if DATA.exists() else {}


def create(url):
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("only http(s) URLs")
    links = _load()
    code = "".join(secrets.choice(ALPHABET) for _ in range(6))
    while code in links:
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
    links[code] = url
    DATA.write_text(json.dumps(links), "utf-8")
    return code


def resolve(code):
    return _load().get(code)


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/links":
            return self._json(404, {"error": "not found"})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            code = create(data.get("url"))
        except (ValueError, AttributeError):
            return self._json(400, {"error": "invalid url"})
        self._json(201, {"code": code, "short": f"/{code}"})

    def do_GET(self):
        url = resolve(self.path.lstrip("/"))
        if url is None:
            return self._json(404, {"error": "unknown code"})
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__" and sys.argv[1:2] == ["serve"]:
    HTTPServer(("127.0.0.1", int(sys.argv[2])), Handler).serve_forever()
'''},
}


@pytest.mark.parametrize("task", bt.TASKS, ids=lambda t: t.id)
def test_task_is_solvable_and_not_already_solved(task, tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    root = br._setup(task, tmp_path)
    ok, _ = br._check(task, root)
    assert not ok, "the starting files must fail the hidden tests"
    for p, c in REFERENCE[task.id].items():
        (root / p).write_text(c, "utf-8")
    ok, out = br._check(task, root)
    assert ok, out
