# Copyright 2016 Google Inc. All Rights Reserved.
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


"""Generates fontdiff HTML input with all glyphs shared by two fonts.

Usage: "python generate_input.py [font_path_a] [font_path_b] [specimen_path]".
Each glyph will be put on its own line in the output HTML.
"""


import sys

from fontTools import ttLib
from nototools import hb_input


def main(font_path_a, font_path_b, specimen_path):
    generator = hb_input.HbInputGenerator(ttLib.TTFont(font_path_a))
    inputs_a = generator.all_inputs(warn=True)
    generator = hb_input.HbInputGenerator(ttLib.TTFont(font_path_b))
    inputs_b = set(generator.all_inputs(warn=True))

    to_ignore = ('\00', '\02')
    to_replace = (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'))
    out_lines = ['<html>']
    for features, text in [i for i in inputs_a if i in inputs_b]:
        if any(char in text for char in to_ignore):
            continue
        for old, new in to_replace:
            text = text.replace(old, new)
        style = ''
        if features:
            style = (' style="font-feature-settings: %s;"' %
                     ', '.join("'%s'" % f for f in features))
        out_lines.append('<p%s>%s</p>' % (style, text))
    out_lines.append('</html>')
    out_text = '\n'.join(out_lines)

    with open(specimen_path, 'w') as out_file:
        out_file.write(out_text.encode('utf-8'))


if __name__ == '__main__':
    main(*sys.argv[1:])
