{
  lib,
  runCommand,
  writeText,
  python,
  source,
  compiler,
  rom,
  sdkPath,
  readLock,
  environment,
  gnutar,
  gzip,
  libbsd,
  libmd,
}:
{
  src,
  lockFile ? src + "/esp-idf-purifier.lock.json",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = readLock { inherit src lockFile; };
  mirror = environment { inherit lock fetchers; };
  context = writeText "esp-idf-native-context.json" (builtins.toJSON lock.data.native);
  projectSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        "build"
        "managed_components"
        ".esp-idf-purifier"
        "__pycache__"
        "result"
      ]);
  };
  project =
    runCommand "esp-idf-firmware"
      {
        buildInputs = lib.optionals (lock.data.native.target == "linux") [
          libbsd
          libmd
        ];
      }
      ''
        export HOME="$TMPDIR/home" XDG_CACHE_HOME="$TMPDIR/cache"
        export IDF_PATH=${source} IDF_TOOLS_PATH="$TMPDIR/tools"
        export IDF_PYTHON_ENV_PATH=${python} IDF_PYTHON_CHECK_CONSTRAINTS=no
        export IDF_COMPONENT_CACHE_PATH="$TMPDIR/components"
        export ESP_IDF_PURIFIER_MIRROR=file://${mirror}/mirror ESP_IDF_PURIFIER_CONTEXT=${context}
        export ESP_IDF_PURIFIER_INSTALLED=${mirror}/components
        export IDF_TARGET=${lib.escapeShellArg lock.data.native.target} ESP_IDF_VERSION=6.1.0
        export IDF_SKIP_CHECK_SUBMODULES=1 ESP_ROM_ELF_DIR=${rom} SOURCE_DATE_EPOCH=1
        ${lib.optionalString (
          lock.data.native.target == "linux"
        ) ''export CMAKE_PREFIX_PATH="${lib.getLib libbsd}:''${CMAKE_PREFIX_PATH:-}"''}
        export PATH="${compiler}/riscv32-esp-elf/bin:${sdkPath}:$PATH"
        mkdir -p "$HOME"
        cp -r ${projectSource} project
        chmod -R u+w project
        ${python}/bin/python ${../native/build.py} "$PWD/project" "$out" ${python}/bin/python
        ${lib.optionalString doCheck checkCommand}
      '';
  release =
    runCommand "esp-idf-firmware-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - -C ${project} . | gzip -n > "$out/firmware.tar.gz"
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = mirror;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
