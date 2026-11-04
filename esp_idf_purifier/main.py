import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from selection import read_native_lock

from .capture import capture


def run_native(arguments, environment):
    result = subprocess.run(
        [
            os.environ["ESP_IDF_PURIFIER_PYTHON"],
            os.environ["ESP_IDF_PURIFIER_IDF"],
            *arguments,
        ],
        env=environment,
        check=False,
    )
    if result.returncode < 0:
        signal.signal(-result.returncode, signal.SIG_DFL)
        os.kill(os.getpid(), -result.returncode)
    return result.returncode


def main():
    project = Path(os.environ.get("ESP_IDF_PURIFIER_PROJECT", os.getcwd())).resolve()
    native = os.environ.get("ESP_IDF_PURIFIER_COMMAND") == "idf.py"
    arguments = sys.argv[1:] if native else None
    action = "exec"
    target = None
    if native:
        selector = argparse.ArgumentParser(add_help=False)
        selector.add_argument("-C", "--project-dir", type=Path)
        options, _ = selector.parse_known_args(arguments)
        if options.project_dir:
            project = options.project_dir.resolve()
        lock_file = Path(
            os.environ.get(
                "ESP_IDF_PURIFIER_LOCK", project / "esp-idf-purifier.lock.json"
            )
        ).resolve()
        if not lock_file.exists():
            print(
                "warning: no esp-idf-purifier lockfile; using ordinary impure component resolution",
                file=sys.stderr,
            )
            environment = os.environ.copy()
            for name in (
                "ESP_IDF_PURIFIER_CONTEXT",
                "ESP_IDF_PURIFIER_MIRROR",
                "ESP_IDF_PURIFIER_COMPONENTS",
                "ESP_IDF_PURIFIER_PROFILE",
            ):
                environment.pop(name, None)
            raise SystemExit(run_native(arguments, environment))
    else:
        parser = argparse.ArgumentParser(prog="esp-idf-purifier")
        parser.add_argument(
            "action", choices=["lock", "prefetch", "exec", "build", "bundle", "publish"]
        )
        parser.add_argument("--project", type=Path, default=project)
        parser.add_argument("--lock", type=Path)
        parser.add_argument("--target", choices=["esp32c3", "linux"])
        parser.add_argument("--update", action="store_true")
        parser.add_argument("--tag")
        options, arguments = parser.parse_known_args()
        project = options.project.resolve()
        lock_file = (
            options.lock.resolve()
            if options.lock
            else project / "esp-idf-purifier.lock.json"
        )
        target = options.target
        action = options.action
        if arguments[:1] == ["--"]:
            arguments = arguments[1:]
        if action == "lock" and options.update:
            for name in (
                "ESP_IDF_PURIFIER_CONTEXT",
                "ESP_IDF_PURIFIER_MIRROR",
                "ESP_IDF_PURIFIER_COMPONENTS",
                "ESP_IDF_PURIFIER_PROFILE",
            ):
                os.environ.pop(name, None)
            if target is None:
                if (project / "dependencies.lock").exists():
                    target = read_native_lock(project / "dependencies.lock").target
                else:
                    raise ValueError(
                        "Select the configured ESP-IDF target with --target"
                    )
            capture(project, target, os.environ["ESP_IDF_PURIFIER_SDK"], lock_file)
            return
    data = json.loads(lock_file.read_text())
    if data.get("schema") != 1 or data.get("sdk") != os.environ["ESP_IDF_PURIFIER_SDK"]:
        raise ValueError(
            "Unsupported lock or changed SDK; run esp-idf-purifier lock --update"
        )
    current = read_native_lock(project / "dependencies.lock").model_dump(mode="json")
    if current != data["native"]:
        raise ValueError(
            "Native component pins changed; run esp-idf-purifier lock --update"
        )
    if action in {"build", "bundle", "publish"}:
        destination = project / ".esp-idf-purifier" / action
        destination.parent.mkdir(exist_ok=True)
        output = subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--json",
                "--out-link",
                str(destination),
                "--file",
                os.environ["ESP_IDF_PURIFIER_REALIZE"],
                "--argstr",
                "lockPath",
                str(lock_file),
                "--argstr",
                "projectPath",
                str(project),
                "--argstr",
                "target",
                "project" if action == "build" else "release",
            ],
            text=True,
        )
        artifact = Path(json.loads(output)[0]["outputs"]["out"])
        if action != "build":
            artifact /= "firmware.tar.gz"
        if action == "publish":
            if not options.tag:
                raise ValueError("Publishing requires --tag")
            subprocess.run(
                [
                    os.environ.get("ESP_IDF_PURIFIER_GH", "gh"),
                    "release",
                    "upload",
                    options.tag,
                    str(artifact),
                    "--clobber",
                ],
                check=True,
            )
        print(artifact)
        return
    with tempfile.TemporaryDirectory(prefix="esp-idf-frozen-") as directory:
        temporary = Path(directory)
        state = project / ".esp-idf-purifier"
        state.mkdir(exist_ok=True)
        output = subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--json",
                "--out-link",
                str(state / "environment"),
                "--file",
                os.environ["ESP_IDF_PURIFIER_REALIZE"],
                "--argstr",
                "lockPath",
                str(lock_file),
            ],
            text=True,
        )
        profile = Path(json.loads(output)[0]["outputs"]["out"])
        mirror = profile / "mirror"
        managed = state / "components" / profile.name
        managed.mkdir(parents=True, exist_ok=True)
        expected_components = {path.name for path in (profile / "components").iterdir()}
        if {path.name for path in managed.iterdir()} - expected_components:
            raise ValueError(
                "Unexpected managed component state; remove the conflicting cache entry and retry"
            )
        for component in (profile / "components").iterdir():
            destination = managed / component.name
            if destination.exists() or destination.is_symlink():
                if (
                    not destination.is_symlink()
                    or destination.resolve() != component.resolve()
                ):
                    raise ValueError(
                        "Managed component state changed; remove the conflicting cache entry and retry"
                    )
            else:
                destination.symlink_to(component, target_is_directory=True)
        context = temporary / "native-context.json"
        context.write_text(json.dumps(data["native"]))
        environment = os.environ | {
            "ESP_IDF_PURIFIER_CONTEXT": str(context),
            "ESP_IDF_PURIFIER_MIRROR": mirror.as_uri(),
            "IDF_COMPONENT_CACHE_PATH": str(temporary / "cache"),
            "ESP_IDF_PURIFIER_COMPONENTS": str(managed),
            "ESP_IDF_PURIFIER_PROFILE": json.dumps([str(profile), data["sdk"]]),
            "IDF_TOOLS_PATH": str(temporary / "tools"),
            "IDF_TARGET": data["native"]["target"],
        }
        if action in {"prefetch", "lock"}:
            subprocess.run(
                [
                    os.environ["ESP_IDF_PURIFIER_PYTHON"],
                    os.environ["ESP_IDF_PURIFIER_IDF"],
                    "--project-dir",
                    str(project),
                    "--build-dir",
                    str(temporary / "verify-build"),
                    "reconfigure",
                ],
                env=environment,
                stdout=sys.stderr,
                check=True,
            )
            print(mirror)
            return
        if not native:
            environment["ESP_IDF_PURIFIER_PROJECT"] = str(project)
            arguments = ["--project-dir", str(project), *arguments]
        raise SystemExit(run_native(arguments, environment))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"esp-idf-purifier: {error}", file=sys.stderr)
        raise SystemExit(1)
