# apple-emoji-linux
Apple Color Emoji for Linux

![Screenshot](preview.png)

### Getting Started

1.  Clone this repo

```sh
$ git clone git@github.com:samuelngs/apple-emoji-linux.git
```

2.  Install build dependencies

```sh
$ bundle install
```

3.  Now, go to your Mac. Find the font `Apple Color Emoji.ttc` under `/System/Library/Fonts` or `/Library/Fonts` and make a copy of the file to the `source` folder.

4.  Build `AppleColorEmoji.ttf`

```sh
$ make -j
```

### Credits

- https://github.com/github/gemoji
- https://github.com/mattermost/mattermost-webapp
- https://github.com/googlei18n/noto-emoji
- https://github.com/googlei18n/nototools

### Disclaimer

The code provided is for educational purposes only. Apple is a trademark of Apple Inc., registered in the U.S. and other countries.
