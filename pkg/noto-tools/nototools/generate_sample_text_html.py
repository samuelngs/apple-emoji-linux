#!/usr/bin/env python
#
# Copyright 2014 Google Inc. All rights reserved.
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

"""Generate a simple html page with the sample text."""

import argparse
import codecs
import collections
import os
from os import path

from nototools import cldr_data
from nototools import tool_utils

_HTML_HEADER = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Noto Sample Text Table</title>
  <style>
    th { text-align: left }
  </style>
</head>
</body>
"""

_HTML_FOOTER = """</body>
</html>
"""

def generate_table(filename):
  with codecs.open(filename, 'w', 'utf-8') as f:
    script_to_samples = _get_script_to_samples()
    print >> f, _HTML_HEADER
    print >> f, '<table>'
    print >> f, '<tr><th>Script<br/>BCP<th>name<th>type<th>text'

    for script, samples in sorted(script_to_samples.iteritems()):
      script_en = cldr_data.get_english_script_name(script)
      print >> f, '<tr><th colspan=4>%s' % script_en
      for bcp, sample_type, sample_text in samples:
        try:
          lsrv = cldr_data.loc_tag_to_lsrv(bcp)
          lsrv = (lsrv[0], None, lsrv[2], lsrv[3])
          bcp_no_script = cldr_data.lsrv_to_loc_tag(lsrv)
          bcp_en = cldr_data.get_english_language_name(bcp_no_script)
          if not bcp_en:
            bcp_en = 'No name'
          if bcp_en == 'Unknown Language' and sample_type == 'chars':
            bcp_en = '(characters)'
        except:
          print 'could not get english name for %s' % bcp
          bcp_en = bcp

        cols = ['<tr>']
        cols.append(bcp_no_script)
        cols.append(bcp_en)
        cols.append(sample_type)
        cols.append(sample_text)
        print >> f, '<td>'.join(cols)
      print >> f, '<tr><td colspan=4>&nbsp;'
    print >> f, '</table>'
    print >> f, _HTML_FOOTER


def _get_script_to_samples():
  script_to_samples = collections.defaultdict(list)

  sample_dir = tool_utils.resolve_path('[tools]/sample_texts')
  for f in sorted(os.listdir(sample_dir)):
    base, ext = path.splitext(f)
    if ext != '.txt' or '_' not in base:
      print 'skipping', f
      continue
    bcp, sample_type = base.split('_')
    try:
      lang, script, region, variant = cldr_data.loc_tag_to_lsrv(bcp)
    except:
      print 'bcp %s did not parse as lsrv' % bcp
      continue
    if script == 'Latn':
      continue
    script_to_samples[script].append((bcp, sample_type))

  for script, samples in sorted(script_to_samples.iteritems()):
    pref = {}
    for bcp, sample_type in samples:
      if bcp not in pref or sample_type == 'udhr':
        pref[bcp] = sample_type

    full_samples = []
    for bcp, sample_type in sorted(pref.iteritems()):
      filename = '%s_%s.txt' % (bcp, sample_type)
      filepath = path.join(sample_dir, filename)
      with codecs.open(filepath, 'r', 'utf-8') as f:
        sample_text = f.read()
      full_samples.append((bcp, sample_type, sample_text))

    script_to_samples[script] = full_samples

  return script_to_samples


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-o', '--outfile', help='name of output file',
      metavar='file', default='sample_text.html')
  args = parser.parse_args()
  generate_table(args.outfile)

if __name__ == '__main__':
  main()
