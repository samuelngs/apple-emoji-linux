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

"""Interactively generate sample text for a font.

Often in bug reports people will describe text using character names.
Replicating the sample text they describe can be a bit tedious.  This
lets you interactively search characters in the font by name to assemble
a string and save it to a file."""

import argparse
import codecs
import readline

from nototools import coverage
from nototools import unicode_data

from fontTools import ttLib

def _help():
  print ('enter a string to match or one of the following:\n'
         '  \'quit\' to exit,\n'
         '  \'help\' to show these options,\n'
         '  \'names\' for names,\n'
         '  \'dump\' to dump the current text,\n'
         '  \'clear\' to clear the current text,\n'
         '  \'write\' to be prompted for a filename to write the text to.')


def _build_text(name_map, initial_text=''):
  text = initial_text
  print 'build text using map of length %d' % len(name_map)
  while True:
    line = raw_input('> ')
    if not line:
      continue
    if line == 'quit':
      break
    if line == 'help':
      _help()
      continue
    if line == 'names':
      print 'names:\n  ' + '\n  '.join(sorted(name_map.keys()))
      continue
    if line == 'dump':
      print 'dump: \'%s\'' % text
      for cp in text:
        print '%06x %s' % (ord(cp), unicode_data.name(ord(cp)))
      continue
    if line == 'clear':
      text = ''
      continue
    if line == 'write':
      line = raw_input('file name> ')
      if line:
        _write_text(line, text)
      continue

    matches = []
    for name, cp in sorted(name_map.iteritems()):
      if line in name:
        matches.append(name)
    if not matches:
      print 'no match for "%s"'% line
      continue

    if len(matches) == 1:
      print matches[0]
      text += unichr(name_map[matches[0]])
      continue

    # if we match a full line, then use that
    if line in matches:
      print line
      text += unichr(name_map[line])
      continue

    new_matches = []
    for m in matches:
      if line in m.split(' '):
        new_matches.append(m)

    # if we match a full word, and only one line has this full word, use that
    if len(new_matches) == 1:
      print new_matches[0]
      text += unichr(name_map[new_matches[0]])
      continue

    select_multiple = True
    while select_multiple:
      print 'multiple matches:\n  ' + '\n  '.join(
          '[%2d] %s' % (i, n) for i, n in enumerate(matches))
      while True:
        line = raw_input('0-%d or q to skip> ' % (len(matches) - 1))
        if line == 'q':
          select_multiple = False
          break
        try:
          n = int(line)
          break
        except ValueError:
          continue

      if not select_multiple: # q
        break

      if n < 0 or n >= len(matches):
        print '%d out of range' % n
        continue

      text += unichr(name_map[matches[n]])
      select_multiple = False

  print 'done.'
  return text


def _get_char_names(charset):
  name_map = {}
  if charset:
    for cp in charset:
      try:
        name = unicode_data.name(cp)
      except:
        name = None
      if not name or name == '<control>':
        name = '%04x' % cp
      else:
        name = '%04x %s' % (cp, name.lower())
      name_map[name] = cp

  return name_map


def _write_text(filename, text):
  with codecs.open(filename, 'w', 'utf-8') as f:
    f.write(text)
  print 'wrote %s' % filename


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-f', '--font',
      help='font whose character map to restrict text to',
      required=True)
  parser.add_argument(
      '-t', '--text',
      help='initial text, prepend @ to read from file')

  args = parser.parse_args()
  if args.text:
    if args.text[0] == '@':
      with codecs.open(args.text[1:], 'r', 'utf-8') as f:
        text = f.read()
    else:
      text = args.text
  else:
    text = ''

  if args.font:
    charset = coverage.character_set(args.font)
    name_map = _get_char_names(charset)
    text = _build_text(name_map, text)
    print 'text: ' + text
  else:
    charset = None


if __name__ == '__main__':
    main()
