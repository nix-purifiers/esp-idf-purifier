{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  python = import ./build-esp-idf-project/python-sdk.nix { inherit pkgs; };
  source = import ./build-esp-idf-project/idf-source.nix { inherit pkgs; };
  compiler = import ./build-esp-idf-project/compiler.nix { inherit pkgs; };
  rom = import ./build-esp-idf-project/rom.nix { inherit pkgs; };
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  cli = scope.callPackage ./cli/default.nix { inherit nixpkgsSrc purifierSrc; };
  readLock = import ../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; };
  buildEspIdfProject = scope.callPackage ./build-esp-idf-project/default.nix { };
  environment = scope.callPackage ./build-esp-idf-project/environment.nix { };
  sdk = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      providers = pkgs.lib.genAttrs [
        "../cli/default.nix"
        "python-sdk.nix"
        "manager.nix"
        "compiler.nix"
        "host-compiler.nix"
        "rom.nix"
        "idf-source.nix"
      ] (name: builtins.hashFile "sha256" (./build-esp-idf-project + ("/" + name)));
      native = builtins.mapAttrs (name: _: builtins.hashFile "sha256" (../native + ("/" + name))) (
        pkgs.lib.filterAttrs (_: type: type == "regular") (builtins.readDir ../native)
      );
    }
  );
  hostCompiler = scope.callPackage ./build-esp-idf-project/host-compiler.nix { };
  sdkPath = pkgs.lib.makeBinPath [
    scope.python
    pkgs.cmake
    pkgs.ninja
    pkgs.git
    scope.hostCompiler
    pkgs.pkg-config
  ];
})
