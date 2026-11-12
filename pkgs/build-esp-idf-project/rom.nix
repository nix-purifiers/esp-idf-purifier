{ pkgs }:
let
  tools = builtins.fromJSON (builtins.readFile ../../native/tool-selection.json);
  selected = builtins.head (
    builtins.filter (tool: tool.name == "esp-rom-elfs")
      tools.${if pkgs.stdenv.hostPlatform.system == "aarch64-linux" then "linux-arm64" else "linux-amd64"}
  );
  archive = pkgs.fetchurl { inherit (selected) url sha256; };
in
pkgs.runCommand "esp-idf-native-rom-elfs"
  {
    nativeBuildInputs = [
      pkgs.gnutar
      pkgs.gzip
    ];
  }
  ''
    mkdir -p "$out"
    tar -xf ${archive} -C "$out" --strip-components=1
  ''
