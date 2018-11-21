#!/usr/bin/env python
#
# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Copy downloaded font zip files from Adobe into noto directory structure.

This leverages some properties of the font drops. The drops come in
zip files that look like this, if you select the Noto Sans CJK subfolder from
the Adobe Sans Version x.xxx folder on google drive and ask to download it:
  Noto_Sans_CJK-yyyy-mm-dd.zip

This reflects the date of the download. For each zip of this type we build
a root named for the date in the drops subdir of the adobe_data tree.

The drops contain a multi-level tree:
  OTF-Fallback (these are for Android and don't go in to Noto)
  OTC (the ttc fonts, weight specific and ginormous)
  OTF-Subset (language-specific subsets, 7 weights each)
    JP (e.g. NotoSansJP-Thin.otf)
    KR
    SC
    TC
  OTF (language defaults, 7 weights plus 2 mono weights each)
    JP (e.g. NotoSansCJKjp-Thin.otf, NotoSansMonoCJKjp-Regular.otf)
    KR
    SC
    TC

The data built under the drops subdir is flat, and does not include the
fallback files.

The Noto zips from Adobe don't have any other files in them (Adobe puts their
metadata in the Source Han Sans directory). This assumes the zip is only the
Noto directory.
"""

__author__ = "dougfelt@google.com (Doug Felt)"

import argparse
import os
import os.path
import re
import shutil
import sys
import zipfile

import notoconfig
import grab_download

def unzip_to_directory_tree(drop_dir, filepath):
  skip_re = re.compile('.*/OTF-Fallback/.*')
  zf = zipfile.ZipFile(filepath, 'r')
  print 'extracting files from %s to %s' % (filepath, drop_dir)
  count = 0
  for name in zf.namelist():
    # skip names representing portions of the path
    if name.endswith('/'):
      continue
    # skip names for data we don't use
    if skip_re.match(name):
      continue
    # get the blob
    try:
      data = zf.read(name)
    except KeyError:
      print 'did not find %s in zipfile' % name
      continue
    dst_file = os.path.join(drop_dir, os.path.basename(name))
    with open(dst_file, 'wb') as f:
      f.write(data)
    count += 1
    print 'extracted \'%s\'' % name
  print 'extracted %d files' % count


def main():
  params = {
      'default_srcdir': os.path.expanduser('~/Downloads'),
      'default_dstdir': notoconfig.values.get('adobe_data'),
      'default_regex': r'Noto_Sans_CJK-\d{4}-\d{2}-\d{2}\.zip'
  }
  grab_download.invoke_main(
      src_vendor='Adobe',
      name_date_re=re.compile(r'(.*)-(\d{4})-(\d{2})-(\d{2})\.zip'),
      extract_fn=unzip_to_directory_tree,
      default_params=params)


if __name__ == "__main__":
    main()
