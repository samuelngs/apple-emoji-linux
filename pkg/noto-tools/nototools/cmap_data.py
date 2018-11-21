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

import collections
import datetime

from nototools import noto_fonts # for script_name_for_report
from nototools import tool_utils

from xml.etree import ElementTree as ET

"""Functions for reading/writing cmap data in xml format.

This data is represented by a CmapData object, which consists of MetaData
and TableData.  MetaData consists of the date, the program name, and args,
which is a list of arg, value tuples.  TableData consists of a list of
headers, and a list of RowData objects with fields named after the headers.

Currently the cmap data metadata holds information about how the data was
generated, and the table the generated data.  There are four or six
columns: script code, script name, the number of codepoints, and the
codepoints represented as a string of hex values and ranges separated by
space; when there are six columns these are the count and ranges of
'fallback codepoints'. This format is not enforced by all the related
functions in this file, though it is used by the code that converts between
a map from script to cpset and a TableData."""

MetaData = collections.namedtuple('MetaData', 'date, program, args')
TableData = collections.namedtuple('TableData', 'header, rows')
CmapData = collections.namedtuple('CmapData', 'meta, table')


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


def _read_meta(meta_node):
  """Return a MetaData object for the 'meta' element."""
  date = meta_node.get('date')
  program = meta_node.get('program')
  args = []
  args_node = meta_node.find('args')
  if args_node is not None:
    for arg_node in args_node:
      key = arg_node.tag
      val = arg_node.get('val').strip()
      args.append((key, val))
  return MetaData(date, program, args)


def _read_table(table_node):
  """Return a TableData object for the 'table' element."""
  header = []
  rows = []
  for node in table_node:
    if node.tag == 'th':
      if header:
        raise ValueError('cannot handle multiple headers')
      elif rows:
        raise ValueError('encountered header after rows')
      else:
        header = node.text.strip()
    elif node.tag == 'tr':
      rows.append(node.text.strip())
  return create_table(header, rows)


def _read_tree(root):
  """Return a CmapData object for the 'cmapdata' element."""
  meta = _read_meta(root.find('meta'))
  table = _read_table(root.find('table'))
  return CmapData(meta, table)


def _build_meta(metadata):
  """Create an xml 'meta' element for the MetaData object."""
  meta = ET.Element('meta', date=metadata.date, program=metadata.program)
  if metadata.args:
    args = ET.Element('args')
    for k, v in metadata.args:
      arg = ET.Element(k, {'val': v})
      args.append(arg)
    meta.append(args)
  return meta


def _build_table(tabledata):
  """Create an xml 'table' element for the TableData object."""
  table = ET.Element('table', nrows=str(len(tabledata.rows)))
  if tabledata.header:
    header = ET.Element('th')
    header.text = ','.join(tabledata.header)
    table.append(header)
  for rowdata in tabledata.rows:
    row = ET.Element('tr')
    row_items = [getattr(rowdata, h, '') for h in tabledata.header]
    row.text = ','.join(row_items)
    table.append(row)
  return table


def _build_tree(cmap_data, pretty=False):
  """Create an xml 'cmapdata' element for the CmapData object."""
  root = ET.Element('cmapdata')
  def opt_append(elem):
    if elem != None:
      root.append(elem)
  opt_append(_build_meta(cmap_data.meta))
  opt_append(_build_table(cmap_data.table))
  if pretty:
    _prettify(root)
  return ET.ElementTree(element=root)


def read_cmap_data_file(filename):
  return _read_tree(ET.parse(filename).getroot())


def read_cmap_data(text):
  return _read_tree(ET.fromstring(text))


def write_cmap_data_file(cmap_data, filename, pretty=False):
  _build_tree(cmap_data, pretty).write(
      filename, encoding='utf-8', xml_declaration=True)


def write_cmap_data(cmap_data, pretty=False):
  return ET.tostring(_build_tree(cmap_data, pretty).getroot(), encoding='utf-8')


def create_metadata(program, args=None, date=datetime.date.today()):
  """Create a MetaData object from the program, args, and date."""
  return MetaData(
      str(date), program,
      [] if not args else [(str(arg[0]), str(arg[1])) for arg in args])


def create_table(header, rows):
  """Create a TableData object from the header and rows.  Header
  is a string, rows is a list of strings.  In each, columns are
  separated by ',' which cannot otherwise appear in the text.
  Each row must have the same number of columns as the header does."""
  header = [t.strip() for t in header.split(',')]
  RowData = collections.namedtuple('RowData', header)
  rowdatas = []
  for row in rows:
    row = [t.strip() for t in row.split(',')]
    if len(row) != len(header):
      raise ValueError('table has %d cols but row[%d] has %d' % (
          len(header), len(rowdatas), len(row)))
    rowdatas.append(RowData(*row))
  return TableData(header=header, rows=rowdatas)


def create_table_from_map(script_to_cmap):
  """Create a table from a map from script to cmaps.  Outputs
  the script code, script name, count of code points, the
  codepoint ranges in hex separated by space, the count of
  excluded/fallback code points, and their ranges separated by
  space.  script_to_cmap can have values either of cmap or of
  a tuple of cmap, xcmap; in the first case xcmap is assumed
  None.  xcmaps that are None are marked as having an xcount of -1.
  This makes it possible to distinguish an empty xcmap from one
  that doesn't exist."""

  table_header = 'script,name,count,ranges,xcount,xranges'.split(',')
  RowData = collections.namedtuple('RowData', table_header)

  table_rows = []
  for script in sorted(script_to_cmap):
    cmap = script_to_cmap.get(script)
    xcmap = None
    if type(cmap) == tuple:
      xcmap = cmap[1]
      cmap = cmap[0]
    name = noto_fonts.script_name_for_report(script)
    count = len(cmap)
    cp_ranges = tool_utils.write_int_ranges(cmap)
    if xcmap == None:
      xcount = -1
      xcp_ranges = ''
    else:
      xcount = len(xcmap)
      xcp_ranges = tool_utils.write_int_ranges(xcmap)
    table_rows.append(
        RowData(script, name, str(count), cp_ranges, str(xcount),
                xcp_ranges))
  return TableData(table_header, table_rows)


def create_map_from_table(table):
  """Create a map from script code to cmap."""
  assert table.header[0:4] == 'script,name,count,ranges'.split(',')
  return {rd.script: rd for rd in table.rows}


def _test():
  meta =  create_metadata('test', [('this', 5), ('that', 12.3)])
  table = create_table('foo,bar', [
      '1,5.3',
      '2,6.4',
      ])
  cmapdata = CmapData(meta, table)
  print cmapdata
  xml_text = write_cmap_data(cmapdata)
  newdata = read_cmap_data(xml_text)
  print newdata
  write_cmap_data_file(cmapdata, 'test_cmap_data.xml', pretty=True)
  newdata = read_cmap_data_file('test_cmap_data.xml')
  print newdata


if __name__ == "__main__":
  _test()
