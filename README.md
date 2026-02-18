![AppleColorEmojiLinux](https://repository-images.githubusercontent.com/158348890/44a361ad-d9f3-4b7b-8b57-fd3198ec9952)

# apple-emoji-ttf

Brings Apple’s vibrant color emojis to Linux and Windows.

## Disclaimer

This project and all its source code, information, and instructions are for educational purposes only. All Apple Color Emoji assets and designs belong to Apple. Apple is a registered trademark of Apple Inc. in the U.S. and other countries.

## Known or potential issues

1. **Firefox** — May not display the font correctly due to limited support for CBDT/CBLC color bitmap fonts (Linux and Windows).
2. **Windows** — In testing the font works with Notepad, PowerShell, and Edge, but there is no guarantee it will work in all applications.


## Putting the font on Linux

### Ubuntu / Debian

Download the `.deb` from [Releases](https://github.com/samuelngs/apple-emoji-ttf/releases) and install it:

```bash
sudo dpkg -i fonts-apple-color-emoji.deb
# or
sudo apt install ./fonts-apple-color-emoji.deb
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
# Put AppleColorEmoji-Linux.ttf in that folder (from releases or from your build output).
```

So that apps actually use it for emoji, fontconfig has to prefer Apple Color Emoji. Two things help:

1. **Emoji family** — In `/etc/fonts/conf.d/60-generic.conf` (or your distro’s equivalent), find the `<alias>` for `<family>emoji</family>`. In the `<prefer>` list inside it, make sure `<family>Apple Color Emoji</family>` is first. It’s often already in the list; if so, move it to the very front. If it’s not there, add it at the top so it’s chosen before Noto, Segoe, etc.

2. **Your own config** — Create `~/.config/fontconfig/fonts.conf` (create the directory if it doesn’t exist). You can copy the repo’s `fonts.conf` into that path. It tells fontconfig to prefer Apple Color Emoji for serif, sans-serif, and monospace, and to use it when an app asks for Noto Color Emoji.

Then clear the font cache: `fc-cache -fv`.

## Putting the font on Windows

Download the Windows build from releases or build with `--target windows`. The font is set up to replace Segoe UI Emoji.

The file to replace is exactly `C:\Windows\Fonts\seguiemj.ttf`. Back up the original first if you want to keep it. From an elevated Command Prompt you can try a direct copy; if Windows has the file locked, use this instead:

```cmd
takeown /f "C:\Windows\Fonts\seguiemj.ttf"
icacls "C:\Windows\Fonts\seguiemj.ttf" /grant administrators:F
del "C:\Windows\Fonts\seguiemj.ttf"
copy "AppleColorEmoji-Windows.ttf" "C:\Windows\Fonts\seguiemj.ttf"
```

Then restart so all apps pick up the new font.

Keep in mind using a font from a different OS may have licensing implications; that’s on you.

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
