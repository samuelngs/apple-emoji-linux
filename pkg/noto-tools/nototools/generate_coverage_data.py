#!/usr/bin/env python
#
# Copyright 2016 Google Inc. All rights reserved.
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

import argparse
import collections
import datetime
from os import path
import sys

from nototools import cmap_data
from nototools import coverage
from nototools import tool_utils

from xml.etree import ElementTree as ET

"""Generate a coverage.xml file listing the codepoints covered by
a font family plus a name."""

MetaData = collections.namedtuple('MetaData', 'date,program,args')
CmapData = collections.namedtuple('CmapData', 'name,ranges')
CoverageData = collections.namedtuple('CoverageData', 'metadata,cmapdata')


def get_cps_from_files(paths):
  """Return a tuple of the cps and the paths that we actually read."""
  cps = set()
  new_paths = set()
  for f in paths:
    ext = path.splitext(f)[1]
    if ext not in ['.otf', '.ttf']:
      continue
    cps |= coverage.character_set(f)
    new_paths.add(f)
  return cps, sorted(new_paths)


def get_cps_from_cmap_data_file(data_file):
  cps = set()
  data = cmap_data.read_cmap_data_file(data_file)
  for row in data.table.rows:
    cps |= tool_utils.parse_int_ranges(row.ranges)
  return cps


def _create_metadata(**kwargs):
  """Create a MetaData object from the args.  'date' defaults to today's
  date."""
  date = str(kwargs.pop('date', datetime.date.today()))
  program = str(kwargs.pop('program', 'generate_coverage_data'))
  arglist = [
      (k, v) for k, v in sorted(kwargs.iteritems())
      if v is not None]
  return MetaData(date, program, arglist)


def _create_cmapdata(name, cmap):
  """Create a CmapData object from the name and cmap."""
  return CmapData(name, tool_utils.write_int_ranges(cmap))


def create(name, cps, paths=None, cmap_data=None):
  """Generate the coverage data object."""
  metadata = _create_metadata(paths=paths, cmap_data=cmap_data)
  cmapdata = _create_cmapdata(name, cps)
  return CoverageData(metadata, cmapdata)


def _common_path_prefix(items):
  """Assuming items is an array of paths using path.sep as a path separator,
  return a common path prefix of the items."""
  prefix = None
  if len(items) <= 1:
    return ''
  for item in items:
    if prefix is None:
      last = item.rfind(path.sep)
      if last < 0:
        return ''
      prefix = item[:last + 1]
      continue
    end = len(item)
    while True:
      last = item.rfind(path.sep, 0, end)
      if last < 0:
        return ''
      item_prefix = item[:last + 1]
      if prefix == item_prefix:
        break
      if prefix.startswith(item_prefix):
        prefix = item_prefix
        break
      end = last
  return prefix


def _build_meta_elem(metadata):
  """Convert metadata to ET node."""
  meta = ET.Element('meta', date=metadata.date, program=metadata.program)
  if metadata.args:
    args = ET.Element('args')
    for k, v in metadata.args:
      if isinstance(v, list):
        arg = ET.Element(k, isList='true')
        # handle items that are path names
        prefix = _common_path_prefix(v)
        plen = 0
        if prefix:
          arg.set('prefix', prefix)
          plen = len(prefix)
        for item in v:
          item_elem = ET.Element('item')
          item_elem.text=str(item)[plen:]
          arg.append(item_elem)
      else:
        arg = ET.Element(str(k), val=str(v))
      args.append(arg)
    meta.append(args)
  return meta


def _build_cmap_elem(cmapdata):
  """Convert data to ET node."""
  data = ET.Element('data')
  name = ET.Element('name')
  name.text = cmapdata.name
  data.append(name)
  ranges = ET.Element('ranges')
  ranges.text = cmapdata.ranges
  data.append(ranges)
  return data


def _prettify(root, indent=''):
  """Pretty-print the root element if it has no text and children
     by adding to the root text and each child's tail."""
  if not root.text and len(root):
    indent += '  '
    sfx = '\n' + indent
    root.text = sfx
    for elem in root:
      elem.tail = sfx
      _prettify(elem, indent)
    elem.tail = sfx[:-2]


def _build_tree(coveragedata):
  root = ET.Element('coveragedata')
  root.append(_build_meta_elem(coveragedata.metadata))
  root.append(_build_cmap_elem(coveragedata.cmapdata))
  _prettify(root)
  return ET.ElementTree(element=root)


def write(coveragedata, out_file=None):
  """Write coverage data to xml."""
  tree = _build_tree(coveragedata)
  if out_file:
    tree.write(out_file, encoding='utf-8', xml_declaration=True)
  else:
    print ET.tostring(tree.getroot(), encoding='utf-8')


def _read_meta(meta_elem):
  date = meta_elem.get('date')
  program = meta_elem.get('program')
  args = []
  args_node = meta_elem.find('args')
  if args_node is not None:
    for arg_node in args_node:
      key = arg_node.tag
      if arg_node.attrib.get('isList', False):
        prefix = arg_node.attrib.get('prefix', '')
        val = []
        for item in arg_node.findall('item'):
          val.append(prefix + item.text)
      else:
        val = arg_node.get('val').strip()
      args.append((key, val))
  return MetaData(date, program, args)


def _read_data(data_elem):
  name = data_elem.find('name').text.strip()
  ranges = data_elem.find('ranges').text.strip()
  return CmapData(name, ranges)


def _read_tree(root_elem):
  meta = _read_meta(root_elem.find('meta'))
  data = _read_data(root_elem.find('data'))
  return CoverageData(meta, data)


def read(coveragefile):
  return _read_tree(ET.parse(coveragefile).getroot())


def main():
  default_coverage_file = '[tools]/nototools/data/noto_cmap_phase3.xml'

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-o', '--output_file', help='name of xml file to output', metavar='file')
  parser.add_argument(
      '-d', '--dirs', help='directories containing font files', metavar='dir',
      nargs='+')
  parser.add_argument(
      '-f', '--files', help='font files', metavar='file', nargs='+')
  parser.add_argument(
      '-n', '--name', help='short name of this collection, used in reports',
      metavar='name', required=True)
  parser.add_argument(
      '-c', '--cmap_data', help='cmap data file (default %s)' %
      default_coverage_file, const=default_coverage_file, nargs='?',
      metavar='file')
  args = parser.parse_args()

  cmap_path = None
  if args.dirs or args.files:
    paths = tool_utils.collect_paths(args.dirs, args.files)
    cps, paths = get_cps_from_files(paths)
  elif args.cmap_data:
    cmap_path = tool_utils.resolve_path(args.cmap_data)
    cps = get_cps_from_cmap_data_file(cmap_path)
    paths = None
  else:
    print 'Please specify font files, directories, or a cmap data file.'
    return
  coverage = create(args.name, cps, paths=paths, cmap_data=cmap_path)
  write(coverage, args.output_file)


if __name__ == '__main__':
  main()
