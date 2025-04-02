![AppleColorEmojiLinux](https://repository-images.githubusercontent.com/158348890/44a361ad-d9f3-4b7b-8b57-fd3198ec9952)

# Apple Color Emoji for Linux

Welcome to the world of colorful emojis on your Linux system! 🌈 This project brings Apple's vibrant emojis to your Linux experience.

## Disclaimer

🚨 Before we get started, please note that this project is for educational purposes only. Apple is a trademark of Apple Inc., registered in the U.S. and other countries.

## 🚀 Installing Prebuilt AppleColorEmoji Font

- 🔗 Download the [latest release](https://github.com/samuelngs/apple-emoji-linux/releases/latest/download/AppleColorEmoji.ttf) of `AppleColorEmoji.ttf` from our [Release Page](https://github.com/samuelngs/apple-emoji-linux/releases)
- 📁 Copy `AppleColorEmoji.ttf` to `~/.local/share/fonts`.
- 🔄 Rebuild the font cache with `fc-cache -f -v`.
- 🎉 Voila! You're all set to embrace the world of expressive emojis!

## 🛠 Building AppleColorEmoji from source

You can decide to use the provided [flake.nix](./flake.nix) to automatically get the dependencies, or install the dependencies manually on your system and build from source:

### Manually installing dependencies

- 🐍 Install Python 3; the process currently requires a Python 3.x wide build.
- 📦 Install the [fonttools Python package](https://github.com/fonttools/fonttools): `python -m pip install fonttools`
- 📦 Install the [nototools Python package](https://github.com/googlei18n/nototools): `python -m pip install https://github.com/googlefonts/nototools/archive/v0.2.1.tar.gz`, or clone from [here](https://github.com/googlei18n/nototools) and follow the instructions.
- 🛠 Install image optimization tools: [Optipng](http://optipng.sourceforge.net/), [Zopfli](https://github.com/google/zopfli), [Pngquant](https://pngquant.org/), and [ImageMagick](https://www.imagemagick.org/).
  - On RedHat-based systems: `yum install optipng zopfli pngquant imagemagick`
  - On Fedora: `dnf install optipng zopfli pngquant imagemagick`
  - On Debian or Ubuntu: `apt-get install optipng zopfli pngquant imagemagick`
- 🔄 Clone the [source repository](https://github.com/samuelngs/apple-emoji-linux) from GitHub.
- 🖥 Open a terminal, navigate to the directory, and type `make -j` to build `AppleColorEmoji.ttf` from source.
- ⚙️ To install the built `AppleColorEmoji.ttf` to your system, run `make install`.
- 🔄 Rebuild your system font cache with `fc-cache -f -v`.

### Using Nix

- Install Nix and ensure flakes are enabled (look for `experimental-features = nix-command flakes` in your `nix.conf`). You can use the [Lix installer](https://lix.systems/install/) if you do not already have a working Nix install.
- Clone the [source repository](https://github.com/samuelngs/apple-emoji-linux) from GitHub.
- Navigate to the directory in a terminal and run `nix build` to start the build.
- The built `AppleColorEmoji.ttf` will be in the `./result/share/fonts/truetype` folder.

## 🌟 Using AppleColorEmoji

AppleColorEmoji uses the CBDT/CBLC color font format, which is supported by Android and Chrome/Chromium OS. Windows supports it starting with Windows 10 Anniversary Update in Chrome and Edge. On macOS, only Chrome supports it, while on Linux, it will support it with some fontconfig tweaking.

## 🎨 Color Emoji Assets

Uncover the assets used to craft AppleColorEmoji, showcasing the diverse world of emojis. Note: some characters share assets, particularly gender-neutral ones. Refer to the `emoji_aliases.txt` file for aliasing definitions.

🚨 Please be aware that images in the font may differ from the original assets, with flag images being PNGs featuring standardized sizes and creative transforms.

## 🙌 Credits

- [googlei18n/noto-emoji](https://github.com/googlei18n/noto-emoji)
- [googlei18n/nototools](https://github.com/googlei18n/nototools)

## 📜 License

- Emoji fonts (under the fonts subdirectory) are under the [SIL Open Font License, version 1.1](fonts/LICENSE).
- Tools and some image resources are under the [Apache license, version 2.0](./LICENSE).
