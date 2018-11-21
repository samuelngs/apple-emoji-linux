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

"""Extract attribution data from the ohchr UDHR site."""

# This tool generates a .tsv file of attribution data based on information at the ohchr
# site, but first you have to manually extract that data from the html on the site, as
# there's no convenient way to get it.  This block of comments describes the process.
#
# The idea is to find out which data on the ohchr site is 'official United Nations' data
# and which is not.  The data itself doesn't say, so we need to look at the attributions
# listed on the ohchr.org site.
#
# Note that the data we actually use is not directly from ohchr.org, but from
# www.unicode.org/udhr.  That site has cleaned up the data a little and converted it to
# xml format.  We are assuming that any data with a matching language code shares the
# original attribution, but we could be wrong.  The unicode.org site does not have the
# attribution data in any kind of organized form.  Instead, they put a comment at the top
# of each document giving copyright to "The Office of the High Commisioner for Human
# Rights."
#
# Unfortunately, the data at www.ohchr.org is not readily available.  At
# http://www.ohchr.org/EN/UDHR/Pages/SearchByLang.aspx you can page through the data using
# the dropdown under 'Search by Translation', but there's no visible url for a single page
# or for the data as a whole.
#
# If you try to view each page and then 'save as...', chrome fetches the url for the page
# it is showing, which returns the first (default) page no matter what data you are
# actually viewing.  'View as source' works, but it provides a formatted page, and if you
# choose 'save as...' from there, you get the source for that formatted page, not the raw
# source.  The only way to get the source is to select and copy it from the source view
# into another document.
#
# At this point it makes more sense to just grab the portion of the data we can use
# instead of the whole file.  So the process is to use the dropdown to show one of the
# pages of translations and then choose view source for it.  Copy the contents of the
# <table> tag that lists the languages and sources into a stub html file.  Repeat this for
# each of the six dropdown pages.  The stub contains a single table element with the id
# 'ohchr_alldata', after this the table contains the data from all six ohchr pages.
#
# This data is still odd, in particular it nests <tr> and <td> tags.  Fortunately
# HTMLParser doesn't care, and we don't need to care.  The three pieces of data are the
# 'ohchr code', the 'language name', and the 'source'.  The ohchr code is how they link to
# the page for the translation, mostly it is a three-letter language code but sometimes it
# is just whatever their server uses.  The 'language name' is more or less an English
# translation of the language, sometimes with notes on script or region or the native name
# of the language, and the attribution is a string.  The data is structured so that the
# ohchr code is part of an anchor tag that wraps the language string, and the source is
# part of a span in the following td.  There are no other anchor tags or spans in the
# data, so we can just look for these.  Separating each set is a close tr tag, so we can
# emit the data then.
#
# The output is a list of records with tab-separated fields: ohchr_code, lang_name, and
# source_name.  The udhr index at unicode.org references the 'ohchr' code, so this is how
# we tie the attributions to the data from unicode.org.


import argparse
import codecs
import HTMLParser as html
import re

from nototools import tool_utils

class ParseOhchr(html.HTMLParser):
  def __init__(self, trace=False):
    html.HTMLParser.__init__(self)
    self.trace = trace
    self.result_list = []
    self.restart()

  def restart(self):
    self.margin = ''
    self.state = 'before_table'
    self.tag_stack = []
    self.collect_lang = False
    self.collect_source = False
    self.ohchr_code = ''
    self.lang_name = ''
    self.source_name = ''

  def results(self):
    return self.result_list

  def indent(self):
    self.margin += '  '

  def outdent(self):
    if not self.margin:
      print '*** cannot outdent ***'
    else:
      self.margin = self.margin[:-2]

  def get_attr(self, attr_list, attr_id):
    for t in attr_list:
      if t[0] == attr_id:
        return t[1]
    return None

  def handle_starttag(self, tag, attrs):
    if tag not in ['link', 'meta', 'area', 'img', 'br']:
      if self.trace:
        print self.margin + tag + '>'
      self.tag_stack.append((tag, self.getpos()))
      self.indent()
    elif self.trace:
      print self.margin + tag

    if self.state == 'before_table' and tag == 'table':
      table_id = self.get_attr(attrs, 'id')
      if table_id == 'ohchr_alldata':
        self.state = 'in_table'
    elif self.state == 'in_table':
      if tag == 'tr':
        self.ohchr_code = ''
        self.lang_name = ''
        self.source_name = ''
      elif tag == 'a':
        a_id = self.get_attr(attrs, 'id')
        if a_id and a_id.endswith('_hpLangTitleID'):
          ohchr_code = self.get_attr(attrs, 'href')
          ix = ohchr_code.rfind('=')
          self.ohchr_code = ohchr_code[ix+1:]
          self.collect_lang = True
      elif tag == 'span':
        span_id = self.get_attr(attrs, 'id')
        if span_id and span_id.endswith('_lblSourceID'):
          self.collect_source = True
      elif tag == 'td':
        self.collect_lang = False
        self.collect_source = False

  def handle_endtag(self, tag):
    while self.tag_stack:
      prev_tag, prev_pos = self.tag_stack.pop()
      self.outdent()
      if tag != prev_tag:
        if self.trace:
          print 'no close tag for %s at %s' % (prev_tag, prev_pos)
      else:
        break
    if self.trace:
      print self.margin + '<'
    if self.state == 'in_table':
      if tag == 'table':
        self.state = 'after_table'
      elif tag == 'tr':
        if self.ohchr_code:
          self.lang_name = re.sub(r'\s+', ' ', self.lang_name).strip()
          self.source_name = re.sub(r'\s+', ' ', self.source_name).strip()
          if not self.source_name:
            self.source_name = '(no attribution)'
          self.result_list.append((self.ohchr_code, self.lang_name, self.source_name))
          self.ohchr_code = ''
          self.lang_name = ''
          self.source_name = ''

  def handle_data(self, data):
    if self.collect_lang:
      self.lang_name += data
    elif self.collect_source:
      self.source_name += data
    pass

def get_ohchr_status(ohchr_code, lang, attrib):
  """Decide the status based on the attribution text.

  'original' are in the public domain and need no attribution.
  'UN' are official UN translations and should be attributed as such.
  'other' are not official UN translations and should be attributed as such."""

  if ohchr_code in ['eng', 'frn', 'spn', 'rus', 'chn', 'arz']:
    return 'original'
  if (attrib.find('United Nations') != -1 or
      attrib.find('High Commissioner for Human Rights') != -1):
    return 'UN'
  return 'other'

def parse_ohchr_html_file(htmlfile, outfile):
  parser = ParseOhchr(False)
  with open(htmlfile) as f:
    parser.feed(f.read())

  lines = []
  for ohchr_code, lang, attrib in parser.results():
    s = get_ohchr_status(ohchr_code, lang, attrib)
    lines.append('\t'.join([ohchr_code, s, lang, attrib]))
  data = '\n'.join(lines) + '\n'

  print 'outfile: "%s"' % outfile
  if not outfile or outfile == '-':
    print data
  else:
    with open(outfile, 'w') as f:
      f.write(data)

def main():
  default_input = '[tools]/third_party/ohchr/ohchr_all.html'
  default_output = '[tools]/third_party/ohchr/attributions.tsv'

  parser = argparse.ArgumentParser()
  parser.add_argument('--src', help='input ohchr html file (default %s)' % default_input,
                      default=default_input, metavar='file', dest='htmlfile')
  parser.add_argument('--dst', help='output tsv file (default %s)' % default_output,
                      default=default_output, metavar='file', dest='outfile')
  args = parser.parse_args()

  htmlfile = tool_utils.resolve_path(args.htmlfile)
  outfile = tool_utils.resolve_path(args.outfile)

  parse_ohchr_html_file(htmlfile, outfile)

if __name__ == '__main__':
    main()
