{
  description = "Convert Apple Color Emoji (sbix TTC) to CBDT/CBLC TTF for Linux and Windows";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    # Pass your TTC when building the package, e.g.:
    #   nix build --input ttc /path/to/Apple\ Color\ Emoji.ttc
    ttc = {
      url = "./Apple Color Emoji.ttc";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, flake-utils, ttc }:
  flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
    in
  {
    devShells = {
      default = pkgs.mkShell {
        nativeBuildInputs = [
          (pkgs.python313.withPackages (ps: [ ps.fonttools ps.pyyaml ps.uharfbuzz ps.pillow ]))
        ];
        shellHook = ''
          echo "Run: python cli.py -c configs/linux.yaml [--input /path/to/Apple\\ Color\\ Emoji.ttc] [--output output/AppleColorEmoji.ttf]"
        '';
      };
    };

    packages.default = pkgs.stdenv.mkDerivation {
      pname = "apple-emoji-ttf";
      version = "0.1.0";
      src = self;

      nativeBuildInputs = [
        (pkgs.python313.withPackages (ps: [ ps.fonttools ps.pyyaml ps.uharfbuzz ps.pillow ]))
      ];

      buildPhase = ''
        runHook preBuild
        python cli.py -c configs/linux.yaml --input "${ttc}" --output ./AppleColorEmoji-Linux.ttf
        python cli.py -c configs/windows.yaml --input "${ttc}" --output ./AppleColorEmoji-Windows.ttf
        runHook postBuild
      '';

      installPhase = ''
        runHook preInstall
        mkdir -p $out/share/fonts/truetype
        cp ./AppleColorEmoji-Linux.ttf ./AppleColorEmoji-Windows.ttf $out/share/fonts/truetype/
        runHook postInstall
      '';

      meta = with pkgs.lib; {
        description = "Apple Color Emoji as CBDT/CBLC TTF for Linux and Windows";
        homepage = "https://github.com/samuelngs/apple-emoji-ttf";
        license = licenses.mit;
        maintainers = [ ];
        platforms = platforms.unix;
      };
    };
  });
}
