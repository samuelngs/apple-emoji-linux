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

"""Generate sample text based on a range given on the command line."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import sys

def char_rep_to_code(char_rep):
    """Converts a character representation in hex to its code."""
    return int(char_rep, 16)

def main(argv):
    """Outputs a space-separated list of characters based on input ranges."""
    chars = []
    for arg in argv[1:]:
        if '-' in arg:
            hyphen_index = arg.index('-')
            code1 = char_rep_to_code(arg[:hyphen_index])
            code2 = char_rep_to_code(arg[hyphen_index+1:])
            chars += range(code1, code2+1)
        else:
            chars.append(char_rep_to_code(arg))
    chars = u' '.join([unichr(code) for code in chars])
    print chars.encode('UTF-8')

if __name__ == '__main__':
    main(sys.argv)
