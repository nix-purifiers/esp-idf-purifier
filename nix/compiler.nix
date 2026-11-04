{ pkgs }:
let
  tools = builtins.fromJSON (builtins.readFile ../native/tool-selection.json);
  selected = builtins.head (
    builtins.filter (tool: tool.name == "riscv32-esp-elf")
      tools.${if pkgs.stdenv.hostPlatform.system == "aarch64-linux" then "linux-arm64" else "linux-amd64"}
  );
  archive = pkgs.fetchurl { inherit (selected) url sha256; };
in
pkgs.stdenv.mkDerivation {
  pname = "esp-idf-native-riscv-compiler";
  inherit (selected) version;
  src = archive;
  sourceRoot = ".";
  dontConfigure = true;
  dontBuild = true;
  nativeBuildInputs = [ pkgs.autoPatchelfHook ];
  buildInputs = [
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
    pkgs.libxml2
    pkgs.ncurses
  ];
  installPhase = ''
    mkdir -p "$out"
    cp -r riscv32-esp-elf "$out/"
  '';
}
