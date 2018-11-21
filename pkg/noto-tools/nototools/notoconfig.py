#!/usr/bin/env python
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

"""Read config file for noto tools.  One could also just define some
environment variables, but using Python for this lets you keep your
environment and shell prefs clean.

This expects a file named '.notoconfig' in the users home directory.
It should contain lines consisting of a name, '=' and a path.  The
expected names are 'noto_tools', 'noto_fonts', 'noto_cjk',
'noto_emoji', and 'noto_source'.  The values are absolute paths
to the base directories of these noto repositories.

Formerly these were a single repository so the paths could all be reached
from a single root, but that is no longer the case.
"""

import os
from os import path

_ERR_MSG = """
Could not find ~/.notoconfig or /usr/local/share/noto/config.

Nototools uses this file to locate resources it uses, since many resources
such as fonts and sample_texts are not installed in locations relative
to the nototools python files and scripts.

Please create one of the above config files containing a line like the
following, where the absolute path to the root of the git repo on your
machine follows the '=' character:

  noto_tools=/path/to/root/of/nototools

If you use any of the other noto repos, add similar lines for 'noto_emoji',
'noto_fonts', 'noto_cjk', 'noto_source', or 'noto_fonts_alpha'.
"""

_values = {}
_config_path = None  # so we know

def _setup():
  """The config consists of lines of the form <name> = <value>.
  values will hold a mapping from the <name> to value.
  Blank lines and lines starting with '#' are ignored."""
  global _config_path

  paths = [path.expanduser('~/.notoconfig'), '/usr/local/share/noto/config']
  for configfile in paths:
    if path.exists(configfile):
      with open(configfile, "r") as f:
        for line in f:
          line = line.strip()
          if not line or line.startswith('#'):
            continue
          k, v = line.split('=', 1)
          _values[k.strip()] = v.strip()
      _config_path = configfile
      break
  # This needs to be silent.  It causes a makefile error in noto-emoji,
  # which expects stdout to consist only of the output of a python
  # script it runs.

_setup()

# convenience for names we expect.

# By default we allow running without a config, since many small tools don't
# require it.  But if you run code that calls noto_tools and provides no
# default, we assume you do require it and raise an exception.

def noto_tools(default=''):
  """Local path to nototools git repo.  If this is called, we require config
  to be set up."""
  result = _values.get('noto_tools', default)
  if result:
    return result
  raise Exception(_ERR_MSG)

def noto_fonts(default=''):
  """Local path to noto-font git repo"""
  return _values.get('noto_fonts', default)

def noto_cjk(default=''):
  """Local path to noto-cjk git repo"""
  return _values.get('noto_cjk', default)

def noto_emoji(default=''):
  """Local path to noto-emoji git repo"""
  return _values.get('noto_emoji', default)

def noto_source(default=''):
  """Local path to noto-source git repo"""
  return _values.get('noto_source', default)

def noto_fonts_alpha(default=''):
  """Local path to noto-fonts-alpha git repo"""
  return _values.get('noto_fonts_alpha', default)

def get(key, default=''):
  return _values.get(key, default)

if __name__ == '__main__':
  keyset = set(_values.keys())
  if not keyset:
    print 'no keys defined, probably no notoconfig file was found.'
  else:
    wid = max(len(k) for k in keyset)
    fmt = '%%%ds: %%s' % wid
    for k in sorted(keyset):
      print fmt % (k, get(k))
    print 'config: %s' % _config_path
