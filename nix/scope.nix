{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  python = import ./python-sdk.nix { inherit pkgs; };
  source = import ./idf-source.nix { inherit pkgs; };
  compiler = import ./compiler.nix { inherit pkgs; };
  rom = import ./rom.nix { inherit pkgs; };
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  readLock = import ./read-lock.nix { inherit (pkgs) lib; };
  buildEspIdfProject = scope.callPackage ./build-project.nix { };
  environment = scope.callPackage ./environment.nix { };
  sdk = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      providers = pkgs.lib.genAttrs [
        "cli.nix"
        "python-sdk.nix"
        "manager.nix"
        "compiler.nix"
        "host-compiler.nix"
        "rom.nix"
        "idf-source.nix"
      ] (name: builtins.hashFile "sha256" (./. + ("/" + name)));
      native = builtins.mapAttrs (name: _: builtins.hashFile "sha256" (../native + ("/" + name))) (
        pkgs.lib.filterAttrs (_: type: type == "regular") (builtins.readDir ../native)
      );
    }
  );
  hostCompiler = scope.callPackage ./host-compiler.nix { };
  sdkPath = pkgs.lib.makeBinPath [
    scope.python
    pkgs.cmake
    pkgs.ninja
    pkgs.git
    scope.hostCompiler
    pkgs.pkg-config
  ];
})
