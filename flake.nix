{
  description = "Convert Apple Color Emoji (sbix TTC) to CBDT/CBLC TTF for Linux and Windows";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # Pass your TTC when building the package, e.g.:
    #   nix build --input ttc /path/to/Apple\ Color\ Emoji.ttc
    ttc = {
      url = "path:./Apple Color Emoji.ttc";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, ttc }:
    let
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            nativeBuildInputs = [
              (pkgs.python312.withPackages (ps: [ ps.fonttools ]))
            ];
            shellHook = ''
              echo "Run: python convert.py [--input /path/to/Apple\\ Color\\ Emoji.ttc] [--output output/AppleColorEmoji.ttf]"
            '';
          };
        });

      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          apple-emoji-ttf = pkgs.callPackage ./default.nix {
            src = self;
            ttc = ttc;
          };
          default = self.packages.${system}.apple-emoji-ttf;
        });
    };
}
