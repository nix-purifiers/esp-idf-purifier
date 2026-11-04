{ pkgs }:
let
  python = pkgs.python3Packages;
in
python.buildPythonApplication {
  pname = "idf-component-manager";
  version = "3.1.2";
  pyproject = true;
  src = pkgs.fetchzip {
    url = "https://github.com/espressif/idf-component-manager/archive/621f2530f29021a62cbd54a6d54efa7d717f6334.tar.gz";
    hash = (builtins.fromJSON (builtins.readFile ../native/manager-source-pin.json)).hash;
  };
  build-system = [ python.setuptools ];
  dependencies = with python; [
    psutil
    rich
    rich-click
    esp-pylib
    pyparsing
    ruamel-yaml
    requests
    requests-file
    requests-toolbelt
    jsonref
    pydantic
    pydantic-core
    pydantic-settings
    pathvalidate
    truststore
  ];
  postPatch = "${pkgs.python3}/bin/python3 ${../native/patch-manager.py} .";
  doCheck = false;
  pythonImportsCheck = [
    "idf_component_manager"
    "idf_component_tools"
  ];
}
