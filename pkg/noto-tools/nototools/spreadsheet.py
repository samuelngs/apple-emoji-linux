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
"""Get information from the status spreadsheet with MTI"""

SPREADSHEET_NAME = ('Noto Project Status (Phase II)- go-noto - '
                    'Unicode-Monotype (1).csv')

import argparse
import csv
import os
from os import path
import re

from fontTools import ttLib

from nototools import font_data
from nototools import noto_fonts

def check_spreadsheet(src_file):
  filenames = set()
  prev_script_name = None
  fontdata = {}
  filedata = {}
  with open(src_file) as csvfile:
    reader = csv.DictReader(csvfile)
    for index, row in enumerate(reader):
      font = row['Fonts'].replace('\xc2\xa0', ' ').strip()
      hinting = row['Hinting'].strip()
      status = row['Status'].strip()
      accepted_version = row['Accepted Version'].strip()
      note = row['Note'].strip()

      # family script style (variant UI) weight, mostly
      m = re.match(
          r'Noto (Kufi|Naskh|Color Emoji|Emoji|Sans|Serif|Nastaliq)'
          r'(?: (.*?))?'
          r'(?: (UI))?'
          r' (Thin|Light|DemiLight|Regular|Medium|Bold Italic'
          r'|Bold|Black|Italic)(?: \(merged\))?$',
          font)
      if not m:
        m = re.match(r'Noto (Sans) (Myanmar) (UI)(.*)', font)
        if not m:
          print 'could not parse Myanmar exception: "%s"' % font
          continue

      style, script, ui, weight = m.groups()

      weight = weight or 'Regular'
      weight = weight.replace(' ', '')
      ui = ui or ''
      script = script or ''
      script = re.sub('-| ', '', script)
      style = style.replace(' ', '')
      ext = 'ttf'
      if script == 'CJK':
        ext = 'ttc'
      elif script.startswith('TTC'):
        ext = 'ttc'
        script = ''
      elif script == '(LGC)':
        script = ''
      elif script == 'UI':
        ui = 'UI'
        script = ''
      elif script == 'Phagspa':
        script = 'PhagsPa'
      elif script == 'SumeroAkkadianCuneiform':
        script = 'Cuneiform'

      fontname = ''.join(['Noto', style, script, ui, '-', weight, '.', ext])
      # print '%s:\n--> %s\n--> %s' % (
      #    font, str((style, script, ui, weight)), fontname)

      if not hinting in [
          'hinted',
          'hinted (CFF)',
          'unhinted']:
        print 'unrecognized hinting value \'%s\' on line %d (%s)' % (
            hinting, index, fontname)
        continue
      hinted = 'hinted' if hinting in ['hinted', 'hinted (CFF)'] else 'unhinted'

      if not status in [
          'In finishing',
          'Released w. lint errors',
          'Approved & Released',
          'Approved & Not Released',
          'In design',
          'Design approved',
          'Design re-approved',
          'Released']:
        print 'unrecognized status value \'%s\' on line %d (%s)' % (
            status, index, fontname)
        continue

      expect_font = status in [
          'Released w. lint errors',
          'Approved & Released',
          'Approved & Not Released',
          'Released']

      data = (fontname, (index, font, style, script, ui, weight), hinted,
              status, accepted_version, note, expect_font)
      filedata[hinted + '/' + fontname] = data

    # ok, now let's see if we can find these files
    all_noto = noto_fonts.get_noto_fonts()
    notodata = {
        ('hinted' if f.is_hinted else 'unhinted') + 
        '/' + path.basename(f.filepath) : f
        for f in all_noto
        }
    noto_filenames = frozenset(notodata.keys())
    spreadsheet_filenames = frozenset(k for k in filedata if filedata[k][6])
    spreadsheet_extra = spreadsheet_filenames - noto_filenames
    spreadsheet_missing = noto_filenames - spreadsheet_filenames
    if spreadsheet_extra:
      print 'spreadsheet extra:\n  ' + '\n  '.join(
          sorted(spreadsheet_extra))
    if spreadsheet_missing:
      print 'spreadsheet missing:\n  ' + '\n  '.join(
          sorted(spreadsheet_missing))

    spreadsheet_match = spreadsheet_filenames & noto_filenames
    for filename in sorted(spreadsheet_match):
      data = filedata[filename]
      filepath = notodata[filename].filepath
      ttfont = ttLib.TTFont(filepath, fontNumber=0)
      font_version = font_data.printable_font_revision(ttfont)
      approved_version = data[4]
      if approved_version:
        warn = '!!!' if approved_version != font_version else ''
        print '%s%s version: %s approved: %s' % (
            warn, filename, font_version, approved_version)
      else:
        print '%s version: %s' % (filename, font_version)


def main():
  default_file = path.expanduser(path.join('~/Downloads', SPREADSHEET_NAME))

  parser = argparse.ArgumentParser()
  parser.add_argument('-sf',
                      '--src_file',
                      help='path to tracking spreadsheet csv',
                      metavar='fname',
                      default=default_file)

  args = parser.parse_args()
  check_spreadsheet(args.src_file)


if __name__ == '__main__':
  main()
