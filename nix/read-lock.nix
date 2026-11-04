{ lib }:
{
  src,
  lockFile ? src + "/esp-idf-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  indices = data.indices or { };
  safe =
    path:
    builtins.isString path
    && path != ""
    && !(lib.hasPrefix "/" path)
    && builtins.all (
      part:
      !(builtins.elem part [
        ""
        "."
        ".."
      ])
    ) (lib.splitString "/" path);
  valid =
    (data.schema or null) == 1
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.native or null)
    && builtins.elem (data.native.target or null) [
      "esp32c3"
      "linux"
    ]
    && builtins.isAttrs (data.native.dependencies or null)
    && builtins.isString (data.native.manifest_hash or null)
    && builtins.isList entries
    && builtins.all (
      entry:
      builtins.isAttrs entry
      && safe (entry.path or null)
      && builtins.isString (entry.url or null)
      && lib.hasPrefix "https://" entry.url
      && builtins.isString (entry.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" entry.hash != null
      && (entry.mirrors or null) == [ ]
    ) entries
    && builtins.length (lib.unique (map (entry: entry.path) entries)) == builtins.length entries
    && builtins.isAttrs indices
    && builtins.all (name: safe name && builtins.isString indices.${name}) (builtins.attrNames indices);
in
{
  purifier = "esp-idf";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "ESP-IDF component lock is missing or malformed; run esp-idf-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
