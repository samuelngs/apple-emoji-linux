#! /bin/bash
set -e

# noto uses otf2otc and otc2otf from afdko
# we don't do a full install, the python code issues a shell command using
# the full path to the tool so I think we're ok not messing with the PATH.
cd /app/pkgs
git clone --depth 1 -b master https://github.com/adobe-type-tools/afdko.git

# install noto.  especially for the fonts, we don't need the full history.
mkdir -p /app/noto
cd /app/noto

# get the most recent version of the tools
git clone --depth 1 -b master https://github.com/googlei18n/nototools.git

# we are going to clone at release tags for these, but this configures
# the repos to only know about the tag, not any branches.  So we then
# need to reconfigure and set up a tracking branch for master so it's
# easy to sync up if we want to.  We will leave them at the tag, however.
# these are the latest tags as of 2017-05-19.  This will prune the
# history while letting us have at least one tagged commit and allow us
# to use master if we want, as well as update.
#
# Unfortunately, -q doesn't supporess the warnings about detached HEAD
# when we clone this way.
git clone --depth 1 --branch v2017-05-18-cook-color-fix https://github.com/googlei18n/noto-emoji.git
cd noto-emoji
git config --add remote.origin.fetch +refs/heads/master:refs/remotes/origin/master
git fetch
git branch -t master origin/master
cd ..

git clone --depth 1 --branch v2017-04-25-adlam https://github.com/googlei18n/noto-fonts.git
cd noto-fonts
git config --add remote.origin.fetch +refs/heads/master:refs/remotes/origin/master
git fetch
git branch -t master origin/master
cd ..

git clone --depth 1 --branch v2017-04-03-serif-cjk-1-0 https://github.com/googlei18n/noto-cjk.git
cd noto-cjk
git config --add remote.origin.fetch +refs/heads/master:refs/remotes/origin/master
git fetch
git branch -t master origin/master
cd ..

# setup nototools and install it
cd /app/noto/nototools
pip install -r requirements.txt
python setup.py install

# let noto know where it is located
mkdir -p /usr/local/share/noto
cat << EOF >> /usr/local/share/noto/config
# noto_tools is used to locate sample text data. it's not copied with the
# install so we need to point to it.
noto_tools=/app/noto/nototools
noto_fonts=/app/noto/noto-fonts
noto_cjk=/app/noto/noto-cjk
noto_emoji=/app/noto/noto-emoji
# the ttcutils use afdko via this, we don't do a full install
afdko=/app/pkgs/afdko
EOF
# we usually run as root in docker so this is not strictly necessary...
chmod a+r /usr/local/share/noto/config

# we use 7za when we generate zips for the website data.
#
# some tools expect the en_US.UTF-8 locale to be available, it's not by default.
# we're based on a python image, which is debian not ubuntu, and the available
# package repos don't include language-pack-foo, so do a debian-style install.
# if that image changes we might want to change this.
apt-get update && apt-get install -y locales p7zip-full
cp /etc/locale.gen /etc/locale.gen.bak
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
locale-gen en_US.UTF-8
dpkg-reconfigure -f noninteractive locales
# this won't change our locale if we run bash instead of login.
/usr/sbin/update-locale LANG=en_US.UTF-8

echo "DONE"

