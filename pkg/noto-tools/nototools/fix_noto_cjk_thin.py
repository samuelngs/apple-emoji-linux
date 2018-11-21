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

"""Fix usWeight problem in Noto CJK Thin OTF fonts."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import sys

from fontTools import ttLib

# Increase Version (name table fields 3 and 5, head.fontRevision)
# Change name field 10 to mention we've changed the font
# Change usWeight to 250

def fix_font(source_filename):
    """Create a Windows-specific version of the font."""
    assert source_filename.endswith('.otf')
    font = ttLib.TTFont(source_filename)

    name_table = font['name']
    for record in name_table.names:
        if record.platformID == 1:  # Mac
            assert record.platEncID == 0
            assert record.langID == 0
            encoding = 'Mac-Roman'
        else:  # Windows
            assert record.platformID == 3
            assert record.platEncID == 1
            assert record.langID == 0x0409
            encoding = 'UTF-16BE'
        value = unicode(record.string, encoding)
        if record.nameID == 3:
            original_version = value[:value.index(';')]
            new_version = original_version + '1'
            new_value = value.replace(original_version, new_version, 1)

            # Replace the unique identifier to avoid version conflicts
            assert new_value.endswith('ADOBE')
            new_value = new_value.replace('ADBE', 'GOOG', 1)
            new_value = new_value.replace('ADOBE', 'GOOGLE', 1)
            assert new_value.endswith('GOOGLE')

            assert new_value != value
            record.string = new_value.encode(encoding)
        elif record.nameID == 5:
            new_value = value.replace(original_version, new_version, 1)
            assert new_value != value
            record.string = new_value.encode(encoding)
        elif record.nameID == 10:
            # record #10 appears to be the best place to put a change notice
            assert 'Google' not in value
            new_value = value + ('; Changed by Google '
                                 'to work around a bug in Windows')
            record.string = new_value.encode(encoding)

    font['head'].fontRevision = float(new_version)

    assert font['OS/2'].usWeightClass == 100
    font['OS/2'].usWeightClass = 250

    target_filename = source_filename.replace('.otf', '-Windows.otf')
    font.save(target_filename)


def main(argv):
    """Fix all fonts provided in the command line."""
    for font_filename in argv[1:]:
        fix_font(font_filename)


if __name__ == '__main__':
    main(sys.argv)

