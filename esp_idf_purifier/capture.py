"""Capture native resolution and its native partial-mirror representation."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from idf_component_manager.sync import sync_components
from idf_component_tools.registry.service_details import get_storage_client
from selection import read_native_lock, selected_artifacts


def capture(project, target, sdk, lock_file=None):
    project = Path(project).resolve()
    lock_file = (
        Path(lock_file).resolve()
        if lock_file
        else project / "esp-idf-purifier.lock.json"
    )
    if target not in {"esp32c3", "linux"}:
        raise ValueError("The initial SDK provider supports ESP32-C3 and Linux targets")
    with tempfile.TemporaryDirectory(prefix="esp-idf-capture-") as directory:
        temporary = Path(directory)
        staged = temporary / "project"
        shutil.copytree(
            project,
            staged,
            ignore=shutil.ignore_patterns(
                ".git", ".esp-idf-purifier", "build", "managed_components"
            ),
        )
        environment = os.environ | {
            "IDF_TARGET": target,
            "IDF_TOOLS_PATH": str(temporary / "tools"),
            "IDF_COMPONENT_CACHE_PATH": str(temporary / "cache"),
            "XDG_CACHE_HOME": str(temporary / "cache"),
        }
        for name in (
            "ESP_IDF_PURIFIER_CONTEXT",
            "ESP_IDF_PURIFIER_MIRROR",
            "ESP_IDF_PURIFIER_COMPONENTS",
            "ESP_IDF_PURIFIER_PROFILE",
        ):
            environment.pop(name, None)
        subprocess.run(
            [
                os.environ["ESP_IDF_PURIFIER_PYTHON"],
                os.environ["ESP_IDF_PURIFIER_IDF"],
                "reconfigure",
            ],
            cwd=staged,
            env=environment,
            check=True,
        )
        native = read_native_lock(staged / "dependencies.lock")
        mirror = temporary / "mirror"
        mirror.mkdir()
        specs = []
        entries = []
        fetched_files = {}
        # The SDK performs version selection and URL construction. Nix records
        # the original bytes independently of the native component content hash.
        for name, version, record in selected_artifacts(native):
            specs.append(f"{name}=={version}")
            for key, path in [
                ("download_url", record["url"]),
                ("checksums_url", record["checksums"]),
            ]:
                if path.startswith("/") or ".." in Path(path).parts:
                    raise ValueError("Unsafe native mirror artifact path")
                prefetched = json.loads(
                    subprocess.check_output(
                        ["nix", "store", "prefetch-file", "--json", record[key]],
                        text=True,
                    )
                )
                fetched_files[path] = prefetched["storePath"]
                entries.append(
                    {
                        "path": path,
                        "url": record[key],
                        "hash": prefetched["hash"],
                        "mirrors": [],
                    }
                )
        if specs:
            sync_components(
                get_storage_client("https://components.espressif.com/"),
                staged,
                mirror,
                components=specs,
            )
        for relative, fetched in fetched_files.items():
            destination = mirror / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fetched, destination)
        indices = (
            {
                path.relative_to(mirror).as_posix(): path.read_text()
                for path in (mirror / "components").glob("*/*.json")
            }
            if specs
            else {}
        )
        data = {
            "schema": 1,
            "sdk": sdk,
            "native": native.model_dump(mode="json"),
            "entries": entries,
            "indices": indices,
        }
        context = temporary / "native-context.json"
        context.write_text(json.dumps(data["native"]))
        shutil.rmtree(staged / "managed_components", ignore_errors=True)
        replay_environment = environment | {
            "ESP_IDF_PURIFIER_MIRROR": mirror.as_uri(),
            "ESP_IDF_PURIFIER_CONTEXT": str(context),
            "IDF_COMPONENT_CACHE_PATH": str(temporary / "replay-cache"),
        }
        subprocess.run(
            [
                os.environ["ESP_IDF_PURIFIER_PYTHON"],
                os.environ["ESP_IDF_PURIFIER_IDF"],
                "--build-dir",
                str(temporary / "replay-build"),
                "reconfigure",
            ],
            cwd=staged,
            env=replay_environment,
            check=True,
        )
        for filename, content in [
            (project / "dependencies.lock", (staged / "dependencies.lock").read_text()),
            (lock_file, json.dumps(data, indent=2, sort_keys=True) + "\n"),
        ]:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=filename.parent, prefix=".esp-idf-lock-", delete=False
            ) as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(output.name, filename)
        return data
