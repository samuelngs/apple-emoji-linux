#!/usr/bin/env python
#
# Copyright 2017 Google Inc. All rights reserved.
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

"""Generate html page with waterfalls for a number of fonts."""

import argparse
import codecs
import os
from os import path
import re
import shutil

from nototools import lang_data
from nototools import noto_fonts
from nototools import tool_utils

def _add_styles(lines, prefix, font_names, font_sizes):
  lines.append(prefix + '<style>')

  for i, font_name in enumerate(font_names):
    lines.append(prefix + '  @font-face {')
    lines.append(
        prefix + '    font-family: "font_%d"; src: url("fonts/%s");' % (
            i, font_name))
    lines.append(prefix + '  }')
  lines.append('')

  for i in range(len(font_names)):
    lines.append(prefix + '  .f%d { font-family: "font_%d" }' % (i, i))
  lines.append('')

  for i, s in enumerate(font_sizes):
    lines.append(prefix + '  .s%d { font-size: %dpx }' % (i, s))
  lines.append('')

  lines.append(prefix + '  th { font-size: 14px }')
  lines.append(prefix + '  td { white-space: nowrap }')

  lines.append(prefix + '</style>')


_JS_LINES = """
<script>
  function _font_select(target) {
    var index = target.value.substring(1)
    _show_div(index)
  }

  function _show_div(index) {
    var div_name = "div_" + index
    var divs = document.getElementsByTagName("div")
    for (var i = 0; i < divs.length; i++) {
      var div = divs[i]
      if (div.id.startsWith("div_")) {
        var display = div.id == div_name ? "block" : "none"
        div.style.display = display
      }
    }
  }
</script>"""

def _add_js(lines, prefix):
  for line in _JS_LINES.splitlines():
    line = line.rstrip()
    if line:
      lines.append(prefix + line)
    else:
      lines.append('')


def _add_example(lines, prefix, index, name, sizes, text):
  lines.append(prefix + '<div id="div_%d">' % index)
  lines.append(prefix + '  <h3>%s</h3>' % name)
  lines.append(prefix + '  <table>')
  for i, s in enumerate(sizes):
    lines.append(prefix + '    <tr><th>%dpx:<td class="f%d s%d">%s' % (
        s, index, i, text))
  lines.append(prefix + '  </table>')
  lines.append(prefix + '</div>')


def _add_examples(lines, prefix, font_names, font_sizes, text):
  for i, name in enumerate(font_names):
    _add_example(lines, prefix, i, name, font_sizes, text)


def _add_example_switch(lines, prefix, font_names):
  lines.append(prefix + '<p>Select font')
  lines.append(prefix + '<select name="font_select" '
               'onchange="_font_select(this)">')
  for i, name in enumerate(font_names):
    lines.append(prefix + '  <option value="f%d">%s</option>' % (i, name))
  lines.append(prefix + '</select>')


def _write_html(directory, font_names, font_sizes, text, out_file):
  lines = [
      '<html lang="en">',
      '  <head>',
      '    <meta charset="utf-8">',
      '    <title>Font specimens</title>']
  _add_styles(lines, '    ', font_names, font_sizes)
  _add_js(lines, '    ')
  lines.append('  </head>')

  lines.append('  <body onload="_show_div(0)">')
  _add_example_switch(lines, '    ', font_names)
  _add_examples(lines, '    ', font_names, font_sizes, text)
  lines.append('  </body>')

  lines.append('</html>')
  lines.append('')

  html_text = '\n'.join(lines)
  if out_file:
    with codecs.open(out_file, 'w', 'utf-8') as f:
      f.write(html_text)
    print 'wrote %s' % out_file
  else:
    print html_text


def _get_font_list(root, name_str):
  match_re = re.compile(r'.*%s.*\.(?:ttf|otf)$' % name_str)
  font_list = []
  for d in [root, path.join(root, 'hinted'), path.join(root, 'unhinted')]:
    if path.isdir(d):
      font_list.extend(
          path.join(d, f)[len(root)+1:] for f in os.listdir(d)
          if match_re.match(f))
  return sorted(font_list)


def _get_sample_text(directory, font_names, lang):
  script_keys = set()
  scripts = set()
  for name in font_names:
    noto_font = noto_fonts.get_noto_font(path.join(directory, name))
    if noto_font.script not in script_keys:
      script_keys.add(noto_font.script)
      scripts |= noto_fonts.script_key_to_scripts(noto_font.script)

  if lang:
    lang_scripts = ['%s-%s' % (lang, script) for script in scripts]
  else:
    lang_scripts = [
        '%s-%s' % (lang_data.script_to_default_lang(script), script)
        for script in scripts]
  lang_scripts.extend('und-%s' % script for script in scripts)

  samples = []
  sample_dir = tool_utils.resolve_path('[tools]/sample_texts')
  for f in os.listdir(sample_dir):
    for lang_script in lang_scripts:
      if f.startswith(lang_script):
        samples.append(f)
        break

  print sorted(samples)
  # limit to scripts supported by all fonts
  selected = []
  for sample in samples:
    sample_supported=True
    for script_key in script_keys:
      script_key_supported = False
      for script in noto_fonts.script_key_to_scripts(script_key):
        if '-%s_' % script in sample:
          script_key_supported = True
          break
      if not script_key_supported:
        sample_supported = False
        break
    if sample_supported:
      selected.append(sample)
  if not selected:
    raise Exception('no sample supported by all fonts')
  samples = selected

  # limit to udhr ones if any exist
  selected = [s for s in samples if '_udhr' in s]
  if selected:
    samples = selected
  # limit to non-'und' ones if any exist
  selected = [s for s in samples if not s.startswith('und-')]
  if selected:
    samples = selected
  if len(samples) != 1:
    raise Exception (
        'found %d sample files (%s) but need exactly 1' % (
            len(samples), ', '.join(sorted(samples))))
  print 'selected sample %s' % samples[0]

  with codecs.open(path.join(sample_dir, samples[0]), 'r', 'utf-8') as f:
    text = f.read()
  return text.strip()


def generate(root, font_str, font_sizes, text, lang, out_file):
  root = tool_utils.resolve_path(root)
  if not path.isdir(root):
    raise Exception('%s is not a directory' % root)

  font_names = _get_font_list(root, font_str)
  if not font_names:
    raise Exception('no fonts matching "%s" in %s' % (font_str, root))

  print 'found %d fonts under %s:\n  %s' % (
      len(font_names), root, '\n  '.join(sorted(font_names)))

  if not font_sizes:
    font_sizes = [10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24, 28, 32]

  if not text:
    text = _get_sample_text(root, font_names, lang)

  if out_file:
    out_file = path.abspath(out_file)
    file_dir = tool_utils.ensure_dir_exists(path.dirname(out_file))
    if path.exists(out_file):
      print 'file %s already exists, overwriting' % out_file
    font_dir = tool_utils.ensure_dir_exists(path.join(file_dir, 'fonts'))
    for font_name in font_names:
      src = path.join(root, font_name)
      dst = tool_utils.ensure_dir_exists(
          path.dirname(path.join(font_dir, font_name)))
      shutil.copy2(src, dst)

  _write_html(root, font_names, font_sizes, text, out_file)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-r', '--root', help='directory containing fonts, optionally in '
      'hinted/unhinted subdirs', default='[fonts]', required=True,
      metavar='dir')
  parser.add_argument(
      '-n', '--name_str', help='string to match font name', required=True,
      metavar='str')
  parser.add_argument(
      '-t', '--text', help='text to use, defaults to udhr text for the '
      'script when there is a common script', metavar='str')
  parser.add_argument(
      '-l', '--lang', help='language string to select among multiple texts '
      'for a script', metavar='lang')
  parser.add_argument(
      '-o', '--out_file', help='name of file to output', nargs='?',
      const='specimens.html', metavar='file')
  parser.add_argument(
      '-s', '--sizes', help='font sizes', nargs='+', type=int,
      metavar='size')
  args = parser.parse_args()
  generate(
      args.root, args.name_str, args.sizes, args.text, args.lang, args.out_file)


if __name__ == '__main__':
  main()
