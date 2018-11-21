#! /bin/bash
set -e

# Note, this assumes the noto workspaces have been mapped under /app/noto such
# that nototools, noto-emoji, noto-fonts, and noto-cjk all have /app/noto as
# their parent.  Use -v when calling docker run to map them.

# noto uses otf2otc and otc2otf from afdko
# we don't do a full install, the python code issues a shell command using
# the full path to the tool so I think we're ok not messing with the PATH.
cd /app/pkgs
git clone --depth 1 -b master https://github.com/adobe-type-tools/afdko.git

# let noto know where it is located
mkdir -p /usr/local/share/noto
cat << EOF >> /usr/local/share/noto/config
# noto_tools is used to locate sample text data. it's not copied with the
# install so we need to point to it.
noto_tools=/app/noto/nototools
noto_fonts_alpha=/app/noto/noto-fonts-alpha
noto_fonts=/app/noto/noto-fonts
noto_cjk=/app/noto/noto-cjk
noto_emoji=/app/noto/noto-emoji
noto_source=/app/noto/noto-source
# the ttcutils use afdko via this, we don't do a full install
afdko=/app/pkgs/afdko
EOF
# we usually run as root in docker so this is not strictly necessary...
chmod a+r /usr/local/share/noto/config

# crate a script to setup nototools and install it, this has to be run in
# an active container that has mapped noto.

# In order to access noto-emoji tools from a different location, we
# need to put it on the path.  The naming is a problem.  We assume here
# that we're in control of the environment so write the PYTHONPATH
# directly.
cat << EOF >> /usr/local/share/noto/setup_nototools
# source this file
pushd /app/noto/nototools
pip install -r requirements.txt
python setup.py develop
popd

export PYTHONPATH=/app/noto/noto-emoji
EOF

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

