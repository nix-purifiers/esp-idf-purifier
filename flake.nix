{
  description = "Locked, Nix-resolved ESP-IDF components";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        esp-idf-purifier = import ./pkgs/default.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (
        system:
        let
          p = (pkgsFor system).esp-idf-purifier;
        in
        {
          default = p.cli;
          python = p.python;
          compiler = p.compiler;
          source = p.source;
          rom = p.rom;
        }
      );
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/esp-idf-purifier";
        };
      });
      lib.esp-idf-purifier = (nixpkgs.lib.extend (import ./lib-overlays/default)).esp-idf-purifier;
      checks = forAll (
        system:
        let
          p = (pkgsFor system).esp-idf-purifier;
          build = p.buildEspIdfProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = ''
              ${p.python}/bin/python -m esptool --chip esp32c3 image-info "$out/purifier_proof.bin" >/dev/null
            '';
          };
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          host =
            (p.buildEspIdfProject {
              src = ./examples/host;
              doCheck = true;
              checkCommand = ''
                "$out/host_proof.elf" > "$TMPDIR/host-output"
                grep -qx answer=42 "$TMPDIR/host-output"
              '';
            }).packages.project;
          cli = p.cli;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
