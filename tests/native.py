"""Exercise native builds, immutable inputs, warm caches and ordinary networking."""

import argparse
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("cli", type=Path)
options = parser.parse_args()
cli = options.cli.resolve() / "bin"
fixture = Path(__file__).resolve().parents[1] / "examples/minimal"
with tempfile.TemporaryDirectory(
    prefix="esp-idf-native-", dir=os.environ.get("TMPDIR")
) as directory:
    temporary = Path(directory)
    project = temporary / "project"
    shutil.copytree(
        fixture,
        project,
        ignore=shutil.ignore_patterns(
            "build",
            "managed_components",
            ".esp-idf-purifier",
            "sdkconfig",
            "sdkconfig.old",
        ),
    )
    lock = project / "dependencies.lock"
    original_lock = lock.read_bytes()
    old_cache = project / "managed_components/espressif__cjson/cJSON"
    old_cache.mkdir(parents=True)
    poison = old_cache / "cJSON.c"
    poison.write_text("#error old ambient cache must not be used\n")

    def run(arguments, expected=0):
        result = subprocess.run(
            arguments, cwd=project, capture_output=True, text=True, check=False
        )
        assert result.returncode == expected, result.stdout + result.stderr
        return result

    source = project / "main/main.c"
    original_source = source.read_text()
    for answer in (42, 43, 42):
        source.write_text(original_source.replace("42", str(answer)))
        result = run([str(cli / "idf.py"), "build"])
        image = (project / "build/purifier_proof.elf").read_bytes()
        assert ('{"answer":' + str(answer) + "}").encode() in image
        assert lock.read_bytes() == original_lock
        assert poison.read_text() == "#error old ambient cache must not be used\n"
        print(
            f"native firmware answer={answer}, same pins and preserved ambient cache: PASS",
            flush=True,
        )
    result = run([str(cli / "idf.py"), "build"])
    assert "Executing action: reconfigure" not in result.stdout
    assert "main/main.c.obj" not in result.stdout, result.stdout
    assert "cJSON/cJSON.c.obj" not in result.stdout, result.stdout
    print("unchanged native incremental build: PASS", flush=True)
    state = project / ".esp-idf-purifier"
    profile = (state / "environment").resolve()
    roots = subprocess.check_output(
        ["nix-store", "--query", "--roots", str(profile)], text=True
    )
    assert str(state / "environment") in roots
    component = next((state / "components" / profile.name).iterdir())
    try:
        (component / "CMakeLists.txt").write_text("modified")
    except OSError:
        pass
    else:
        raise AssertionError("Locked native component is writable")
    component.unlink()
    component.mkdir()
    result = run([str(cli / "idf.py"), "build"], expected=1)
    assert "Managed component state changed" in result.stderr
    component.rmdir()
    print(
        "Nix component immutability, GC root and alias mutation rejection: PASS",
        flush=True,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"root-http-ok")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cmake = project / "CMakeLists.txt"
    original_cmake = cmake.read_text()
    url = f"http://127.0.0.1:{server.server_port}/"
    script = f"import urllib.request; assert urllib.request.urlopen('{url}').read()==b'root-http-ok'"
    cmake.write_text(
        original_cmake
        + '\nexecute_process(COMMAND "$ENV{IDF_PYTHON_ENV_PATH}/bin/python" -c "'
        + script
        + '" COMMAND_ERROR_IS_FATAL ANY)\n'
    )
    try:
        run([str(cli / "idf.py"), "reconfigure"])
    finally:
        cmake.write_text(original_cmake)
        server.shutdown()
        server.server_close()
    print("ordinary root configure HTTP: PASS", flush=True)
    locked_error = run([str(cli / "idf.py"), "--invalid-purifier-option"], expected=2)
    empty = temporary / "empty"
    empty.mkdir()
    fallback = subprocess.run(
        [str(cli / "idf.py"), "--invalid-purifier-option"],
        cwd=empty,
        capture_output=True,
        text=True,
        check=False,
    )
    warning, remaining_stderr = fallback.stderr.split("\n", 1)
    assert "ordinary impure component resolution" in warning
    assert fallback.returncode == locked_error.returncode
    assert fallback.stdout == locked_error.stdout
    assert remaining_stderr == locked_error.stderr
    print("no-lock native stdout/stderr/status preservation: PASS", flush=True)
    manifest = project / "main/idf_component.yml"
    manifest.write_text(manifest.read_text().replace("==1.7.19~2", "^1.7.19"))
    result = run([str(cli / "esp-idf-purifier"), "prefetch"], expected=1)
    assert "Component dependency selection changed" in result.stdout + result.stderr
    print("changed dependency declaration rejected before lookup: PASS", flush=True)
