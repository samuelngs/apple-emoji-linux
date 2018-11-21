#! /bin/bash
set -e

# this is to init the fontconfig cache and our custom fonts.conf
# we also lookup the emoji font, it should be found, and scalable.

cd /app/noto/nototools/nototools
./create_image.py --test
rm *.png *.svg
cd /app/noto
FONTCONFIG_FILE=/app/noto/nototools/fonts.conf fc-match --verbose 'noto color emoji-32'
