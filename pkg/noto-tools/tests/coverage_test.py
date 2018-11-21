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

"""Tests for coverage.py."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import os
from os import path
import tempfile
import unittest

from nototools import coverage
from hb_input_test import make_font


class CharacterSetTest(unittest.TestCase):
    """Test class for coverage.character_set."""
    def test_sanity(self):
        """Test basic sanity of the method."""
        font_file = tempfile.NamedTemporaryFile()
        font = make_font('')
        font.save(font_file.name)
        charset = coverage.character_set(font_file.name)

        self.assertTrue(ord(' ') in charset)
        self.assertTrue(ord('A') in charset)
        self.assertFalse(0x10B00 in charset)


if __name__ == '__main__':
    unittest.main()
