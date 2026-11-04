{ pkgs }:
let
  ps = pkgs.python3Packages;
  sources = builtins.fromJSON (builtins.readFile ../native/sdk-sources.json);
  installed = builtins.fromJSON (builtins.readFile ../native/nix-python-packages.json);
  aliases = {
    "boolean.py" = ps.boolean-py;
    "ruamel.yaml" = ps.ruamel-yaml;
    esptool = ps.toPythonModule pkgs.esptool;
    idf-component-manager = ps.toPythonModule (import ./manager.nix { inherit pkgs; });
  };
  resolve = name: custom.${name} or aliases.${name} or ps.${name};
  extras =
    ps.esp-pylib.optional-dependencies.cli
    ++ ps.esp-pylib.optional-dependencies.ide
    ++ ps.esp-pylib.optional-dependencies.serial;
  custom = pkgs.lib.mapAttrs (
    name: data:
    ps.buildPythonPackage {
      pname = name;
      inherit (data) version;
      pyproject = true;
      src = pkgs.fetchurl { inherit (data) url sha256; };
      build-system = with ps; [
        setuptools
        setuptools-scm
        wheel
        hatchling
        flit-core
      ];
      dependencies = map resolve data.dependencies ++ extras;
      SETUPTOOLS_SCM_PRETEND_VERSION = data.version;
      doCheck = false;
    }
  ) sources;
in
pkgs.python3.withPackages (_: map resolve (builtins.attrNames installed))
