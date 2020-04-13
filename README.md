![AppleColorEmojiLinux](images/screenshot.png)
# Apple Color Emoji for Linux
Color and Black-and-White Apple color emoji fonts, and tools for working with them.

## Disclaimer

The code provided is for educational purposes only. Apple is a trademark of Apple Inc., registered in the U.S. and other countries.

## Installing prebuilt AppleColorEmoji font

- Download the latest release of `AppleColorEmoji.ttf` at the [Release Page](https://github.com/samuelngs/apple-emoji-linux/releases)
- Copy `AppleColorEmoji.ttf` to `~/.local/share/fonts`.
- Rebuild the font cache with `fc-cache -f -v`.
- Now you are set!

## Building AppleColorEmoji from source

- Install Python 2, building `AppleColorEmoji.ttf` currently requires a Python 2.x wide build.
- Install [fonttools python package](https://github.com/fonttools/fonttools).
  - On the command line, enter: `python -m pip install fonttools`
- Install [nototools python package](https://github.com/googlei18n/nototools).
  - On the command line, enter: `python -m pip install https://github.com/googlefonts/nototools/archive/v0.2.1.tar.gz`, or
    clone a copy from https://github.com/googlei18n/nototools and either put it in your PYTHONPATH or use `python setup.py
    develop` ('install' currently won't fully install all the data used by nototools).
- Install [Optipng](http://optipng.sourceforge.net/), [Zopfli](https://github.com/google/zopfli) and [Pngquant](https://pngquant.org/).
  - On RedHat based systems, run `yum install optipng zopfli pngquant`
  - Or on Debian or Ubuntu, you may run `apt-get install optipng zopfli pngquant` at the command line.
- Clone the [source repository](https://github.com/samuelngs/apple-emoji-linux) from Github
- Open a terminal or console prompt, change to the directory where you cloned `apple-emoji-linux`, and type `make -j` to build `AppleColorEmoji.ttf` from source.
- If you wish to install the built `AppleColorEmoji.ttf` to your system, execute `make install`,
- Then rebuild the your system font cache with `fc-cache -f -v`

## Using AppleColorEmoji

AppleColorEmoji uses the CBDT/CBLC color font format, which is supported by Android
and Chrome/Chromium OS.  Windows supports it starting with Windows 10 Anniversary
Update in Chome and Edge.  On macOS, only Chrome supports it, while on Linux it will
support it with some fontconfig tweaking.

## Color emoji assets

The assets provided in the repo are all those used to build the AppleColorEmoji
font.  Note however that AppleColorEmoji often uses the same assets to represent
different character sequences-- notably, most gender-neutral characters or
sequences are represented using assets named after one of the gendered
sequences.  This means that some sequences appear to be missing.  Definitions of
the aliasing used appear in the `emoji_aliases.txt` file.

Also note that the images in the font might differ from the original assets.  In
particular the flag images in the font are PNG images to which transforms have
been applied to standardize the size and generate the wave and border shadow.  We
do not have SVG versions that reflect these transforms.

## Related
- [Apple Color Emoji for Slack on Linux](https://github.com/samuelngs/slack-apple-emoji-linux)

## Credits

- https://github.com/googlei18n/noto-emoji
- https://github.com/googlei18n/nototools

## License

- Emoji fonts (under the fonts subdirectory) are under the [SIL Open Font License, version 1.1](fonts/LICENSE).
- Tools and some image resources are under the [Apache license, version 2.0](./LICENSE).
