"""Consume native exported firmware and check the exact publication asset."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("cli", type=Path)
parser.add_argument("python", type=Path)
options = parser.parse_args()
cli = options.cli.resolve() / "bin/esp-idf-purifier"
python = options.python.resolve() / "bin/python"
fixture = Path(__file__).resolve().parents[1] / "examples/minimal"
with tempfile.TemporaryDirectory(
    prefix="esp-artifact-", dir=os.environ.get("TMPDIR")
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

    def run(arguments, environment=None):
        return subprocess.check_output(
            [str(cli), *arguments, "--project", str(project)],
            text=True,
            env=environment,
        ).strip()

    archive = Path(run(["bundle"]))
    consumer = temporary / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(consumer, filter="data")
    result = subprocess.check_output(
        [
            str(python),
            "-m",
            "esptool",
            "--chip",
            "esp32c3",
            "image-info",
            str(consumer / "purifier_proof.bin"),
        ],
        text=True,
    )
    assert "ESP32-C3" in result and "(valid)" in result, result
    assert (consumer / "bootloader/bootloader.bin").stat().st_size > 0
    assert (consumer / "partition_table/partition-table.bin").stat().st_size > 0
    assert (consumer / "flash_args").stat().st_size > 0
    publication = temporary / "publication.json"
    gh = temporary / "gh"
    gh.write_text(
        "#!"
        + sys.executable
        + "\nimport json,sys\nfrom pathlib import Path\nPath("
        + repr(str(publication))
        + ").write_text(json.dumps(sys.argv[1:]))\n"
    )
    gh.chmod(0o755)
    published = run(
        ["publish", "--tag", "v-proof"], os.environ | {"ESP_IDF_PURIFIER_GH": str(gh)}
    )
    assert published == str(archive)
    assert json.loads(publication.read_text()) == [
        "release",
        "upload",
        "v-proof",
        str(archive),
        "--clobber",
    ]
    external = temporary / "external.lock.json"
    external.write_bytes((project / "esp-idf-purifier.lock.json").read_bytes())
    (project / "esp-idf-purifier.lock.json").unlink()
    external_archive = Path(run(["bundle", "--lock", str(external)]))
    assert external_archive.read_bytes() == archive.read_bytes()
    print("native firmware consumer, exact publication asset and external lock: PASS")
