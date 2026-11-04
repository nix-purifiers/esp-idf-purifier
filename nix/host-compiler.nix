{
  runCommand,
  makeWrapper,
  gcc,
  binutils,
  libbsd,
  libmd,
  lib,
}:
runCommand "esp-idf-host-compiler" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in cc gcc c++ g++; do
    makeWrapper ${gcc}/bin/$name "$out/bin/$name" \
      --add-flags '-I${lib.getDev libbsd}/include -L${lib.getLib libbsd}/lib -L${lib.getLib libmd}/lib -Wl,-rpath,${lib.getLib libbsd}/lib -Wl,-rpath,${lib.getLib libmd}/lib'
  done
  for name in ar ranlib ld nm strip objcopy objdump; do
    ln -s ${binutils}/bin/$name "$out/bin/$name"
  done
''
