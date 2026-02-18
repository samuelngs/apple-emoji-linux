{ pkgs
, src ? ./
, ttc
}:

pkgs.stdenv.mkDerivation {
  pname = "apple-emoji-ttf";
  version = "0.1.0";

  inherit src ttc;

  nativeBuildInputs = [
    (pkgs.python312.withPackages (ps: [ ps.fonttools ]))
  ];

  buildPhase = ''
    runHook preBuild
    python convert.py --input "${ttc}" --target linux --output ./AppleColorEmoji-Linux.ttf
    python convert.py --input "${ttc}" --target windows --output ./AppleColorEmoji-Windows.ttf
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
}
