{
  description = "flake for apple-emoji-linux";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      treefmt-nix,
    }:
    let
      forAllSystems =
        function:
        nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (
          system: function nixpkgs.legacyPackages.${system}
        );

      treefmtConfig = forAllSystems (
        pkgs:
        treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs = {
            nixfmt.enable = true;
            yamlfmt.enable = true;
            ruff-format.enable = true;
            mdformat.enable = true;
          };
          settings.excludes = [
            "*.gitignore"
            "*.lock"
            "*.png"
            "*.pyc"
            "*.txt"
            "*.ttx*"
            "AUTHORS"
            "CONTRIBUTORS"
            "Makefile"
            "LICENSE"
            "third_party/*"
          ];
        }
      );

      buildFromSource =
        {
          stdenv,
          python3,
          optipng,
          zopfli,
          pngquant,
          imagemagick,
          which,
        }:

        stdenv.mkDerivation {
          pname = "apple-emoji-linux";
          version = "17.4";

          src = ./.;

          enableParallelBuilding = true;

          nativeBuildInputs = [
            which
            (python3.withPackages (
              python-pkgs: with python-pkgs; [
                fonttools
                nototools
              ]
            ))
            optipng
            zopfli
            pngquant
            imagemagick
          ];

          installPhase = ''
            runHook preInstall
            mkdir -p $out/share/fonts/truetype
            cp ./AppleColorEmoji.ttf $out/share/fonts/truetype
            runHook postInstall
          '';
        };
    in
    {
      # run `nix fmt` to format all code
      formatter = forAllSystems (pkgs: treefmtConfig.${pkgs.system}.config.build.wrapper);

      # run `nix flake check` to ensure code is formatted
      checks = forAllSystems (pkgs: {
        formatting = treefmtConfig.${pkgs.system}.config.build.check self;
      });

      # run `nix develop` to get dropped into a shell with all the dependencies
      # and `nix build` to build from source
      packages = forAllSystems (pkgs: rec {
        apple-emoji-linux = pkgs.callPackage buildFromSource { };
        default = apple-emoji-linux;
      });
    };
}
