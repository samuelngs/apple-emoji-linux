![AppleColorEmojiLinux](https://repository-images.githubusercontent.com/158348890/3f2bca4c-f858-47b9-bade-1f87a4a313da)

# apple-emoji-ttf

Brings Apple’s vibrant color emojis to Linux and Windows.

## Disclaimer

This project is for educational purposes only. All Apple Color Emoji assets and designs belong to Apple Inc., and Apple is a registered trademark of Apple Inc. in the U.S. and other countries. Using a font from a different operating system may have licensing implications; that responsibility is on you.

## Known or potential issues

1. **Smaller emoji in some Linux apps** — Certain applications may render emoji at a smaller size than expected. This may be related to how the font is built or how specific toolkits handle color fonts. We're still investigating a fix.
2. **Qt applications** — Some Qt-based apps may not render the emoji correctly or at all due to how Qt handles color font tables.
3. **Not usable as a web font (`@font-face`)** — The font uses Apple's `morx` table for shaping instead of the standard `GSUB` table. Browsers that require `GSUB` (or reject CBDT/CBLC-only fonts) will not load it as a web font.

## Putting the font on Linux

### Ubuntu / Debian

Download the `.deb` from [Releases](https://github.com/samuelngs/apple-emoji-ttf/releases) and install it:

```bash
sudo dpkg -i fonts-apple-color-emoji.deb
# or
sudo apt install ./fonts-apple-color-emoji.deb
```

### Fedora / RHEL

Download the `.rpm` from [Releases](https://github.com/samuelngs/apple-emoji-ttf/releases) and install it:

```bash
sudo dnf install ./fonts-apple-color-emoji.rpm
# or
sudo rpm -i fonts-apple-color-emoji.rpm
```

### Arch Linux

Download the `.pkg.tar.zst` from [Releases](https://github.com/samuelngs/apple-emoji-ttf/releases) and install it:

```bash
sudo pacman -U ttf-apple-emoji.pkg.tar.zst
```

### Manual install

Grab `AppleColorEmoji-Linux.ttf` from the repo’s releases (or build it yourself). Put it in your user font folder:

```bash
mkdir -p ~/.local/share/fonts
cp AppleColorEmoji-Linux.ttf ~/.local/share/fonts/
```

So that apps actually use it for emoji, fontconfig has to prefer Apple Color Emoji. Two things help:

1. **Emoji family** — In `/etc/fonts/conf.d/60-generic.conf` (or your distro’s equivalent), find the `<alias>` for `<family>emoji</family>`. In the `<prefer>` list inside it, make sure `<family>Apple Color Emoji</family>` is first. It’s often already in the list; if so, move it to the very front. If it’s not there, add it at the top so it’s chosen before Noto, Segoe, etc.

2. **Your own config** — Create `~/.config/fontconfig/fonts.conf` (create the directory if it doesn’t exist). You can copy the repo’s `fonts.conf` into that path. It tells fontconfig to prefer Apple Color Emoji for serif, sans-serif, and monospace, and to use it when an app asks for Noto Color Emoji.

Then clear the font cache: `fc-cache -fv`.

## Putting the font on Windows

Download the Windows build from releases or build with `--target windows`. The font is set up to replace Segoe UI Emoji.

**Important:** The font file cannot be installed by double-clicking, and Windows font viewer cannot preview it. This is expected. You must replace the system font file manually using the steps below.

Back up the original `C:\Windows\Fonts\seguiemj.ttf` first, then replace it. From an elevated Command Prompt you can try a direct copy; if Windows has the file locked, use this instead:

```cmd
takeown /f "C:\Windows\Fonts\seguiemj.ttf"
icacls "C:\Windows\Fonts\seguiemj.ttf" /grant administrators:F
del "C:\Windows\Fonts\seguiemj.ttf"
copy "AppleColorEmoji-Windows.ttf" "C:\Windows\Fonts\seguiemj.ttf"
```

Then restart so all apps pick up the new font.

## Build the font yourself

Most people can skip this and use the CI-built fonts from the releases. If you want to build the converted font yourself:

**What you need**

- **Python 3.12+**
- **fonttools** — `pip install -r requirements.txt`
- **Apple Color Emoji.ttc** — We don’t provide the font; you can get it from macOS. If you run the script on a Mac, leave the input argument empty and it will use the default TTC path.

**On a Mac** you can run the script with no arguments. It will use the system path for the TTC and write `output/AppleColorEmoji.ttf`:

```bash
pip install -r requirements.txt
python convert.py
```

If your TTC is somewhere else, or you’re on Linux and copied the file over:

```bash
python convert.py --input "/path/to/Apple Color Emoji.ttc" --output output/AppleColorEmoji.ttf
```

`--input` and `--output` are optional; defaults are the macOS path and `output/AppleColorEmoji.ttf`.

Use `--target windows` if you’re building for Windows (Segoe UI Emoji replacement). Other options: `--ppem` (strike size, default 96), `-v` for verbose logs.

## Building with Nix

You can use Nix to get a reproducible environment or to build the font. The TTC file is not shipped with the repo; obtain it from macOS or another source (same as above).

**Dev workflow** — Get a shell with Python 3.12 and fonttools, then run the converter yourself:

- With flakes: `nix develop`, then run `python convert.py` (on macOS with no args, or `python convert.py --input /path/to/Apple\ Color\ Emoji.ttc` elsewhere).
- Without flakes: `nix-shell`, then the same.

**Building the font** — To build the Linux and Windows TTFs and get a store path, you must provide the TTC as a flake input:

```bash
nix build --input ttc /path/to/Apple\ Color\ Emoji.ttc
```

The built fonts will be in `./result/share/fonts/truetype/` (`AppleColorEmoji-Linux.ttf` and `AppleColorEmoji-Windows.ttf`).

## Acknowledgments

This project would not be possible without the help, contributions, and knowledge sharing from the people listed below.

- [@dmlls](https://github.com/dmlls) — Multiple font updates and help with the community
- [@lnking81](https://github.com/lnking81) — Updating font with the latest emojis
- [@win0err](https://github.com/win0err) — Linux installation instructions [(gist)](https://gist.github.com/win0err/9d8c7f0feabdfe8a4c9787b02c79ac51).
- [@jjjuk](https://github.com/jjjuk) — Changes needed for TTF to render correctly on Windows and Windows font installation instructions [(emoji-win)](https://github.com/jjjuk/emoji-win/).
- [@dibenzepin](https://github.com/dibenzepin) and [@typedrat](https://github.com/typedrat) — Nix build support.
