{
  lib,
  runCommand,
  writeText,
  makeWrapper,
  python,
  source,
  compiler,
  rom,
  sdk,
  sdkPath,
  nix,
  gh,
  cacert,
  libbsd,
  nixpkgsSrc,
  purifierSrc,
}:
let
  integration = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../esp_idf_purifier
      ../native
      ./.
    ];
  };
  realize = writeText "esp-idf-purifier-realize.nix" ''
    { lockPath, projectPath ? "", target ? "environment" }:
    let
      pkgs = import (builtins.storePath "${nixpkgsSrc}") {};
      scope = import ${integration}/nix/scope.nix {
        inherit pkgs;
        nixpkgsSrc = builtins.storePath "${nixpkgsSrc}";
        purifierSrc = builtins.storePath "${purifierSrc}";
      };
      lockFile = builtins.toPath lockPath;
      src = builtins.path {
        path = builtins.toPath projectPath;
        name = "esp-idf-project";
        filter = path: type: !(builtins.elem (baseNameOf path) [ ".git" "build" "managed_components" ".esp-idf-purifier" ]);
      };
      build = scope.buildEspIdfProject { inherit src lockFile; };
    in if target == "environment" then scope.environment { lock = scope.readLock { src = dirOf lockFile; inherit lockFile; }; }
       else if target == "project" then build.packages.project
       else if target == "release" then build.release
       else throw "Unknown ESP-IDF purifier target"
  '';
in
runCommand "esp-idf-purifier" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in esp-idf-purifier idf.py; do
    makeWrapper ${python}/bin/python "$out/bin/$name" \
      --add-flags '-m esp_idf_purifier.main' \
      --set PYTHONPATH ${integration}:${integration}/native \
      --set ESP_IDF_PURIFIER_COMMAND "$name" \
      --set ESP_IDF_PURIFIER_PYTHON ${python}/bin/python \
      --set ESP_IDF_PURIFIER_IDF ${source}/tools/idf.py \
      --set ESP_IDF_PURIFIER_SDK ${sdk} \
      --set ESP_IDF_PURIFIER_REALIZE ${realize} \
      --set IDF_PATH ${source} \
      --set IDF_PYTHON_ENV_PATH ${python} \
      --set IDF_PYTHON_CHECK_CONSTRAINTS no \
      --set IDF_SKIP_CHECK_SUBMODULES 1 \
      --set ESP_IDF_VERSION 6.1.0 \
      --set ESP_ROM_ELF_DIR ${rom} \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default NIX_SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --prefix CMAKE_PREFIX_PATH : ${lib.getLib libbsd} \
      --prefix PATH : ${
        lib.makeBinPath [
          nix
          gh
        ]
      }:${compiler}/riscv32-esp-elf/bin:${sdkPath}
  done
''
