let
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixos-unstable.tar.gz") { };
in
pkgs.mkShell {
  nativeBuildInputs = [
    (pkgs.python312.withPackages (ps: [ ps.fonttools ]))
  ];
  shellHook = ''
    echo "Run: python convert.py [--input /path/to/Apple\\ Color\\ Emoji.ttc] [--output output/AppleColorEmoji.ttf]"
  '';
}
