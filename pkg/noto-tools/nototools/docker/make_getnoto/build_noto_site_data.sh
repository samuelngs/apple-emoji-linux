#!/bin/bash

# Build data for get/noto site.

# Map /tmp/website2 to an external location to get the data when this is
# complete.

# Put the repos at the latest tagged release.  This does not do a git pull, we
# assume noto is already at or beyond the latest release.  Might want to rethink
# that.
cd /app/noto/nototools/nototools
./sync_repos.py -v

# Add missing font package to the CJK repo.
# This is too big for github.  Currently we fetch it from the website itself,
# which is kind of circular, since we're building the website...  We need a 
# 'prerelease' location for things like this.
cd /app/noto/noto-cjk
wget https://storage.googleapis.com/noto-website/pkgs/NotoSerifCJK.ttc.zip

# Prepare the emoji font/images.
# This is designed for a tagged release.  We build the emoji font, but don't
# copy it as it should be 'the same' as the one already in the fonts subdir.
# Copying it would make the repo dirty, and generate_website_2_data will
# complain.  Since we only need the images, we don't need to use ZOPFLI
# as the font doesn't matter.  ZOPFLIPNG has to be disabled since it will be
# used by default if present.  We could target the images only but this is
# simpler.
cd /app/noto/noto-emoji
make clean
make -j 8 ZOPFLIPNG= # /app/pkgs/zopfli/zopflipng

# Don't copy, if we're generating a release build of the website this will
# make the repo 'dirty'.
# cp NotoColorEmoji.ttf fonts/

# Generate most of the data.  This requires us to be at tagged releases.
# We don't 'clean' the directory since we expect it might be mapped to one
# outside docker, and when that is the case we can't delete it since it is
# busy.  Probably we should delete the contents instead, right now we 
# depend on the person running the docker environment to ensure the directory
# mapped to is clean.
cd /app/noto/nototools/nototools
./generate_website_2_data.py

# Add the emoji data to the other website data
cd /app/noto/noto-emoji
./generate_emoji_name_data.py -m -1
mkdir -p /tmp/website2/emoji
cp emoji/data.json /tmp/website2/emoji
cp build/compressed_pngs/*.png /tmp/website2/emoji

# /tmp/website2 now holds the data.
echo 'DONE'
