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

"""
Generate a csv with the following columns:
- bcp-47 language code (minimal)
- script (most likely script for the code)
- style name (Serif, Sans, Naskh...)
- ui status (UI, <empty>)
- font name

This will start with a canned list of languages for now. We could 
generate a more comprehensive list from our data.
"""

import collections

import os
from os import path

from nototools import cldr_data
from nototools import noto_fonts

LANGS = (
    'af,am,ar,az,bg,bn,bs,ca,cs,da,de,el,en,en-US,es,es-419,et,eu,fa,fi,'
    'fil,fr,gl,gu,hi,hr,hu,hy,id,is,it,iw,ja,ka,kk,km,kn,ko,ky,lo,lt,lv,'
    'mk,ml,mn,mr,ms,my,ne,nl,no,pa,pl,pt-BR,pt-PT,ro,ru,si,sk,sl,sq,sr,'
    'sv,sw,ta,te,th,tl,tr,uk,ur,uz,vi,zh-CN,zh-TW,zu').split(',')

def accept_font(f):
  return (
      f.family == 'Noto' and  # exclude Arimo, Tinos, Cousine
      f.style != 'Nastaliq' and  # exclude Nastaliq, not suitable for maps
      f.script != 'HST' and  # exclude Historic, tool limitation
      f.weight == 'Regular' and  # to limit members of fonts, we don't
      not f.slope and            #   care about weights
      f.fmt in ['ttf', 'otf'] and  # only support these formats
      (not f.is_cjk or f.subset))  # 'small' language-specific CJK subsets

fonts = filter(accept_font, noto_fonts.get_noto_fonts())
families = noto_fonts.get_families(fonts).values()

def write_csv_header(outfile):
  print >> outfile, 'Code,Script,Style,UI,Font Name'


def write_csv(outfile, lang, script, style, ui, members):
  if members:
    print >> outfile, ','.join(
        [lang, script, style, ui,
         noto_fonts.get_font_family_name(members[0].filepath)])


with open('lang_to_font_table.csv', 'w') as outfile:
  write_csv_header(outfile)
  for lang in LANGS:
    script = cldr_data.get_likely_script(lang)
    found_font = False
    for family in sorted(families, key=lambda f: f.name):
      if script not in noto_fonts.script_key_to_scripts(
          family.rep_member.script):
        continue

      found_font = True
      members = family.hinted_members or family.unhinted_members
      ui_members = [m for m in members if m.is_UI]
      non_ui_members = [m for m in members if not m.is_UI]
      assert len(ui_members) <= 1
      assert len(non_ui_members) <= 1
      write_csv(outfile, lang, script, family.rep_member.style, '',
                non_ui_members)
      write_csv(outfile, lang, script, family.rep_member.style, 'UI',
                ui_members)

    if not found_font:
      print '## no font found for lang %s' % lang
