"""Fresh native capture and failure preservation for both lockfiles."""

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("cli", type=Path)
options = parser.parse_args()
cli = options.cli.resolve() / "bin/esp-idf-purifier"
fixture = Path(__file__).resolve().parents[1] / "examples/minimal"
with tempfile.TemporaryDirectory(
    prefix="esp-capture-", dir=os.environ.get("TMPDIR")
) as directory:
    project = Path(directory) / "project"
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
    command = [
        str(cli),
        "lock",
        "--update",
        "--target",
        "esp32c3",
        "--project",
        str(project),
    ]
    subprocess.run(command, check=True)
    locks = [project / "dependencies.lock", project / "esp-idf-purifier.lock.json"]
    before = [path.read_bytes() for path in locks]
    manifest = project / "main/idf_component.yml"
    manifest.write_text(
        manifest.read_text().replace("==1.7.19~2", "this-is-not-a-version")
    )
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert result.returncode != 0, result.stdout + result.stderr
    assert [path.read_bytes() for path in locks] == before
    print("fresh native capture/replay and failed-capture lock preservation: PASS")
