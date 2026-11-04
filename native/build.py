"""Build with the native SDK and export its own flashing artifact list."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

project = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
python = sys.argv[3]
idf = Path(os.environ["IDF_PATH"]) / "tools/idf.py"
components = os.environ.get("ESP_IDF_PURIFIER_INSTALLED")
if components:
    private = project / ".esp-idf-purifier/components"
    private.mkdir(parents=True, exist_ok=True)
    for component in Path(components).iterdir():
        (private / component.name).symlink_to(component, target_is_directory=True)
    os.environ["ESP_IDF_PURIFIER_COMPONENTS"] = str(private)
subprocess.run([python, str(idf), "--project-dir", str(project), "build"], check=True)
build = project / "build"
description = json.loads((build / "project_description.json").read_text())
flasher_path = build / "flasher_args.json"
flasher = (
    json.loads(flasher_path.read_text())
    if flasher_path.exists()
    else {"flash_files": {}}
)
output.mkdir(parents=True, exist_ok=True)
for relative in flasher["flash_files"].values():
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Native SDK flashing artifact is outside its build directory")
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(build / relative, destination)
for name in ("flash_args", "flasher_args.json"):
    if (build / name).exists():
        shutil.copyfile(build / name, output / name)
elf = Path(description["app_elf"])
if elf.is_absolute():
    elf = elf.relative_to(build)
if ".." in elf.parts:
    raise ValueError("Native SDK ELF artifact is outside its build directory")
shutil.copy2(build / elf, output / elf.name)
