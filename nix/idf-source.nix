{ pkgs }:
let
  basePin = builtins.fromJSON (builtins.readFile ../native/idf-source-pin.json);
  pins = builtins.fromJSON (builtins.readFile ../native/sdk-git-pins.json);
  fetch =
    pin:
    pkgs.fetchzip {
      url = "https://github.com/${pin.repository}/archive/${pin.revision}.tar.gz";
      inherit (pin) hash;
    };
  base = pkgs.fetchzip {
    url = "https://github.com/espressif/esp-idf/archive/fff9895c82d744c7237be8847347bdd1b07c6643.tar.gz";
    inherit (basePin) hash;
  };
in
pkgs.runCommand "esp-idf-linux-c3-source" { } ''
  mkdir -p "$out"
  cp -r ${base}/. "$out/"
  chmod -R u+w "$out"
  cp -r ${fetch pins.mbedtls}/. "$out/components/mbedtls/mbedtls/"
  cp -r ${fetch pins.micro-ecc}/. "$out/components/bootloader/subproject/components/micro-ecc/micro-ecc/"
  cp -r ${fetch pins.tlsf}/. "$out/components/heap/tlsf/"
  cp -r ${fetch pins.lwip}/. "$out/components/lwip/lwip/"
  cp -r ${fetch pins.phy}/. "$out/components/esp_phy/lib/"
  cp -r ${fetch pins.wifi}/. "$out/components/esp_wifi/lib/"
  cp -r ${fetch pins.coex}/. "$out/components/esp_coex/lib/"
  printf '%s\n' v6.1 > "$out/version.txt"
''
