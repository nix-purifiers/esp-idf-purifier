{
  lib,
  runCommand,
  fetchurl,
  fetchgit,
  writeText,
  python3,
  purifier,
  sdk,
  python,
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  archives = purifier.tree (
    {
      name = "esp-idf-component-artifacts";
      inherit
        runCommand
        fetchurl
        fetchgit
        writeText
        python3
        ;
      inherit (checked) entries;
    }
    // fetchers
  );
  context = writeText "esp-idf-native-context.json" (builtins.toJSON lock.data.native);
  indices = lib.mapAttrs (name: text: writeText (baseNameOf name) text) lock.data.indices;
in
assert lib.assertMsg (
  lock.data.sdk == sdk
) "ESP-IDF SDK changed; run esp-idf-purifier lock --update";
runCommand "esp-idf-native-mirror" { } ''
  mkdir -p "$out/mirror" "$out/components"
  cp -r ${archives}/. "$out/mirror/"
  chmod -R u+w "$out/mirror"
  ${lib.concatMapStringsSep "\n" (name: ''
    mkdir -p "$out/mirror"/${lib.escapeShellArg (dirOf name)}
    ln -s ${indices.${name}} "$out/mirror"/${lib.escapeShellArg name}
  '') (builtins.attrNames indices)}
  export IDF_COMPONENT_CACHE_PATH="$TMPDIR/cache" XDG_CACHE_HOME="$TMPDIR/cache"
  export ESP_IDF_PURIFIER_MIRROR="file://$out/mirror"
  ${python}/bin/python ${../native/components.py} ${context} "$out/components"
''
