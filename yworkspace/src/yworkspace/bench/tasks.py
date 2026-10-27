"""yWorkspace Bench tasks: small (fix a bug) → medium (add a feature, build a tool) → large (a small service).
Each task has visible files and HIDDEN tests that are copied in only after the model has finished, so passing
means the work is really right, not that the model edited the tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchTask:
    id: str
    size: str  # small | medium | large
    goal: str
    files: dict[str, str] = field(default_factory=dict)
    hidden: dict[str, str] = field(default_factory=dict)
    check: str = "python -m pytest -q -p no:cacheprovider bench_hidden"
    tags: list[str] = field(default_factory=list)


TASKS = [
    BenchTask("fix-average", "small",
              "The average() function in stats.py returns wrong results. Fix it so it returns the arithmetic mean "
              "and raises ValueError for an empty list. Keep the existing function names.",
              {"stats.py": "def average(values):\n    total = 0\n    for v in values:\n        total += v\n"
                           "    return total / (len(values) - 1)\n\n\ndef spread(values):\n"
                           "    return max(values) - min(values)\n",
               "test_stats.py": "from stats import spread\n\n\ndef test_spread():\n    assert spread([1, 5, 3]) == 4\n"},
              {"bench_hidden/test_hidden_stats.py":
               "import pytest\nfrom stats import average, spread\n\n\ndef test_average():\n"
               "    assert average([2, 4, 6]) == 4\n    assert average([5]) == 5\n    assert average([1.5, 2.5]) == 2\n\n\n"
               "def test_empty():\n    with pytest.raises(ValueError):\n        average([])\n\n\n"
               "def test_spread_untouched():\n    assert spread([3, 9]) == 6\n"},
              tags=["python", "bugfix"]),
    BenchTask("slug-unicode", "small",
              "slugify() in text_utils.py must turn any title into a URL slug: lowercase ASCII letters, digits and "
              "single dashes, no leading/trailing dashes. Turkish letters map to ASCII (ç→c, ğ→g, ı→i, İ→i, ö→o, "
              "ş→s, ü→u). It currently crashes or keeps bad characters.",
              {"text_utils.py": "def slugify(title):\n    return title.lower().replace(' ', '-')\n"},
              {"bench_hidden/test_hidden_slug.py":
               "from text_utils import slugify\n\n\ndef test_basic():\n    assert slugify('Hello World') == 'hello-world'\n\n\n"
               "def test_turkish():\n    assert slugify('Çağrı Şükür İŞ ılık Öğün') == 'cagri-sukur-is-ilik-ogun'\n\n\n"
               "def test_symbols_and_spaces():\n    assert slugify('  A -- B!!  c?  ') == 'a-b-c'\n    assert slugify('') == ''\n"},
              tags=["python", "bugfix", "turkish"]),
    BenchTask("todo-feature", "medium",
              "Add to todo.py: complete(store, item_id) marks an item done (KeyError for unknown ids), pending(store) "
              "returns not-done items in creation order, and save(store, path)/load(path) persist the store as JSON. "
              "Write tests for the new behaviour.",
              {"todo.py": "import itertools\n\n_ids = itertools.count(1)\n\n\ndef new_store():\n    return {}\n\n\n"
                          "def add(store, title):\n    item_id = next(_ids)\n"
                          "    store[item_id] = {\"id\": item_id, \"title\": title, \"done\": False}\n"
                          "    return item_id\n"},
              {"bench_hidden/test_hidden_todo.py":
               "import pytest\nimport todo\n\n\ndef test_complete_and_pending():\n    s = todo.new_store()\n"
               "    a = todo.add(s, 'a')\n    b = todo.add(s, 'b')\n    c = todo.add(s, 'c')\n    todo.complete(s, b)\n"
               "    assert [i['title'] for i in todo.pending(s)] == ['a', 'c']\n    with pytest.raises(KeyError):\n"
               "        todo.complete(s, 999)\n    assert a and c\n\n\n"
               "def test_roundtrip(tmp_path):\n    s = todo.new_store()\n    x = todo.add(s, 'süt al')\n    todo.complete(s, x)\n"
               "    todo.add(s, 'ekmek')\n    p = tmp_path / 's.json'\n    todo.save(s, p)\n    t = todo.load(p)\n"
               "    assert [i['title'] for i in todo.pending(t)] == ['ekmek']\n"
               "    assert any(i['done'] and i['title'] == 'süt al' for i in t.values())\n"},
              tags=["python", "feature"]),
    BenchTask("wordcount-cli", "medium",
              "Create wc.py: `python wc.py FILE` prints three lines: `lines N`, `words N`, `top WORD COUNT` (the most "
              "frequent word, case-insensitive with Turkish rules (İ→i, I→ı), letters including Turkish ones; ties: alphabetical first). "
              "`python wc.py` without a file prints a usage message to stderr and exits with code 2; a missing file "
              "exits with code 1 and a clear message.", {},
              {"bench_hidden/test_hidden_wc.py":
               "import subprocess\nimport sys\n\n\ndef run(*a):\n    return subprocess.run([sys.executable, 'wc.py', *a], "
               "capture_output=True, text=True)\n\n\ndef test_counts(tmp_path):\n    f = tmp_path / 't.txt'\n"
               "    f.write_text('Elma armut\\nelma ÇİLEK elma\\n\\narmut\\n', encoding='utf-8')\n    r = run(str(f))\n"
               "    assert r.returncode == 0\n    assert r.stdout.split('\\n')[:3] == ['lines 4', 'words 6', 'top elma 3']\n\n\n"
               "def test_usage_and_missing():\n    r = run()\n    assert r.returncode == 2 and r.stderr\n"
               "    r = run('yok.txt')\n    assert r.returncode == 1\n"},
              tags=["python", "cli"]),
    BenchTask("shortener-service", "large",
              "Build shortener.py, a small URL shortener with only the standard library. Functions: create(url) "
              "returns a 6-character code (letters/digits) and rejects non-http(s) URLs with ValueError; resolve(code) "
              "returns the URL or None; data is stored in links.json next to the script (path overridable with the "
              "SHORTENER_DATA env var). `python shortener.py serve PORT` starts an HTTP server: POST /api/links with "
              "JSON {\"url\": ...} → 201 {\"code\": ..., \"short\": \"/<code>\"}; GET /<code> → 302 redirect; "
              "unknown code → 404; invalid URL → 400 JSON error. Include tests.", {},
              {"bench_hidden/test_hidden_shortener.py":
               "import json\nimport os\nimport socket\nimport subprocess\nimport sys\nimport time\nimport urllib.error\n"
               "import urllib.request\n\nimport pytest\n\n\n@pytest.fixture()\ndef mod(tmp_path, monkeypatch):\n"
               "    monkeypatch.setenv('SHORTENER_DATA', str(tmp_path / 'd.json'))\n    import importlib\n"
               "    import shortener\n    return importlib.reload(shortener)\n\n\ndef test_functions(mod):\n"
               "    c = mod.create('https://yunuslu.example/a?b=1')\n    assert len(c) == 6 and c.isalnum()\n"
               "    assert mod.resolve(c) == 'https://yunuslu.example/a?b=1'\n    assert mod.resolve('zzzzzz') is None\n"
               "    with pytest.raises(ValueError):\n        mod.create('javascript:alert(1)')\n\n\n"
               "def test_server(tmp_path):\n    s = socket.socket()\n    s.bind(('127.0.0.1', 0))\n    port = s.getsockname()[1]\n"
               "    s.close()\n    env = {**os.environ, 'SHORTENER_DATA': str(tmp_path / 's.json'), 'NO_PROXY': '*'}\n"
               "    p = subprocess.Popen([sys.executable, 'shortener.py', 'serve', str(port)], env=env)\n    try:\n"
               "        for _ in range(50):\n            try:\n                socket.create_connection(('127.0.0.1', port), 0.2).close()\n"
               "                break\n            except OSError:\n                time.sleep(0.1)\n"
               "        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))\n"
               "        req = urllib.request.Request(f'http://127.0.0.1:{port}/api/links', json.dumps({'url': "
               "'https://example.com/x'}).encode(), {'Content-Type': 'application/json'})\n"
               "        r = opener.open(req)\n        assert r.status == 201\n        code = json.loads(r.read())['code']\n"
               "        class NoRedirect(urllib.request.HTTPRedirectHandler):\n"
               "            def redirect_request(self, *a, **k):\n                return None\n"
               "        o2 = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)\n"
               "        with pytest.raises(urllib.error.HTTPError) as e:\n            o2.open(f'http://127.0.0.1:{port}/{code}')\n"
               "        assert e.value.code == 302 and e.value.headers['Location'] == 'https://example.com/x'\n"
               "        with pytest.raises(urllib.error.HTTPError) as e:\n            opener.open(f'http://127.0.0.1:{port}/nope00')\n"
               "        assert e.value.code == 404\n        bad = urllib.request.Request(f'http://127.0.0.1:{port}/api/links', "
               "json.dumps({'url': 'ftp://x'}).encode(), {'Content-Type': 'application/json'})\n"
               "        with pytest.raises(urllib.error.HTTPError) as e:\n            opener.open(bad)\n"
               "        assert e.value.code == 400\n    finally:\n        p.terminate()\n        p.wait(5)\n"},
              tags=["python", "http", "saas"]),
]


def get(task_id: str) -> BenchTask:
    for t in TASKS:
        if t.id == task_id:
            return t
    raise KeyError(task_id)
