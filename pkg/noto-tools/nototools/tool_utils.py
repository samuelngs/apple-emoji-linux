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

"""Some common utilities for tools to use."""

import codecs
import contextlib
import glob
import logging
import os
import os.path as path
import re
import shutil
import subprocess
import sys
import time
import zipfile

from nototools import notoconfig

@contextlib.contextmanager
def temp_chdir(path):
  """Usage: with temp_chdir(path):
    do_something
  """
  saved_dir = os.getcwd()
  try:
    os.chdir(path)
    yield
  finally:
    os.chdir(saved_dir)


noto_re = re.compile(
    r'\[(tools|fonts|fonts_alpha|emoji|cjk|source|adobe|mti|afdko)\](.*)')
def resolve_path(somepath):
  """Resolve a path that might start with noto path shorthand. If
  the path is empty, is '-', or the shorthand is not defined,
  returns None. Example: '[fonts]/hinted'."""

  if not somepath or somepath == '-':
    return None
  m = noto_re.match(somepath)
  if m:
    base, rest = m.groups()
    if base == 'adobe':
      key = 'adobe_data'
    elif base == 'mti':
      key = 'monotype_data'
    elif base == 'afdko':
      key = 'afdko'
    else:
      key = 'noto_' + base
    base = notoconfig.get(key)
    while rest.startswith(path.sep):
      rest = rest[len(path.sep):]
    somepath = path.join(base, rest)
  return path.realpath(path.abspath(path.expanduser(somepath)))


def commonpathprefix(paths):
  """Return the common path prefix and a tuple of the relative subpaths for the
  provided paths.  Uses resolve_path to convert to absolute paths and returns
  the common absolute path.  Some subpaths might be the empty string and joining
  these will produce paths ending in '/', use normpath if you don't want this.

  Python 2.7 only has path.commonprefix, which returns a common string prefix,
  not a common path prefix.
  """
  norm_paths = [resolve_path(p) + path.sep for p in paths]
  prefix = path.dirname(path.commonprefix(norm_paths))
  prefix_len = len(prefix)
  if prefix_len > 1:
    prefix_len += 1 # not '/' so does not end in '/', strip from subpaths
  subpaths = tuple(p[prefix_len:-1] for p in norm_paths)
  return prefix, subpaths


def _name_to_key(keyname):
  if keyname == 'adobe_data':
    return 'adobe'
  if keyname == 'monotype_data':
    return 'mti',
  if keyname.startswith('noto_'):
    return keyname[5:]
  return keyname


def short_path(somepath, basedir=os.getcwd()):
  """Return a short version of somepath, either relative to one of the noto path
  shorthands or to the provided base directory (defaults to current).  For
  logging/debugging output of file paths."""
  shortest = somepath
  if basedir and somepath.startswith(basedir):
    shortest = '.' + somepath[len(basedir):]
  for k, v in notoconfig.values.items():
    if somepath.startswith(v):
      test = ('[%s]' % _name_to_key(k)) + somepath[len(v):]
      if len(test) < len(shortest):
        shortest = test
  return shortest


def check_dir_exists(dirpath):
  if not os.path.isdir(dirpath):
    raise ValueError('%s does not exist or is not a directory' % dirpath)


def check_file_exists(filepath):
  if not os.path.isfile(filepath):
    raise ValueError('%s does not exist or is not a file' % filepath)


def ensure_dir_exists(path, clean=False):
  path = os.path.realpath(path)
  if not os.path.isdir(path):
    if os.path.exists(path):
      raise ValueError('%s exists and is not a directory' % path)
    print "making '%s'" % path
    os.makedirs(path)
  elif clean:
    shutil.rmtree(path)
    os.makedirs(path)
  return path


def generate_zip_with_7za(root_dir, file_paths, archive_path):
  """file_paths is a list of files relative to root_dir, these will be the names
  in the archive at archive_path."""

  arg_list = ['7za', 'a', archive_path, '-tzip', '-mx=7', '-bd', '--']
  arg_list.extend(file_paths)
  with temp_chdir(root_dir):
    # capture but discard output
    subprocess.check_output(arg_list)


def generate_zip_with_7za_from_filepairs(pairs, archive_path):
  """Pairs are source/destination path pairs. The source will be put into the
  zip with name destination."""

  staging_dir = '/tmp/stage_7za'
  if os.path.exists(staging_dir):
    shutil.rmtree(staging_dir)
  os.makedirs(staging_dir)

  pair_map = {}
  for source, dest in pairs:
    if not source.endswith(dest):
      staging_source = os.path.join(staging_dir, dest)
      shutil.copyfile(source, staging_source)
      source_root = staging_dir
    else:
      source_root = source[:-len(dest)]
    if source_root not in pair_map:
      pair_map[source_root] = set()
    pair_map[source_root].add(dest)
  for source_root, dest_set in pair_map.iteritems():
    generate_zip_with_7za(source_root, sorted(dest_set), archive_path)


def dos2unix(root_dir, glob_list):
  """Convert dos line endings to unix ones in place."""
  with temp_chdir(root_dir):
    for g in glob_list:
      file_list = glob.glob(g)
      if file_list:
        subprocess.check_call(['dos2unix', '-k', '-q', '-o'] + file_list)


def zip_extract_with_timestamp(zippath, dstdir):
  zip = zipfile.ZipFile(zippath)
  with temp_chdir(dstdir):
    for info in zip.infolist():
      zip.extract(info.filename)
      # of course, time zones mess this up, so don't expect precision
      date_time = time.mktime(info.date_time + (0, 0, -1))
      os.utime(info.filename, (date_time, date_time))


def git_checkout(repo, branch_or_tag, verbose=False):
  """checkout the branch or tag"""
  with temp_chdir(repo):
    result = subprocess.check_output(
        ['git', 'checkout', branch_or_tag], stderr=subprocess.STDOUT)
    if verbose:
      print '%s:\n%s\n-----' % (repo, result)


def git_mv(repo, old, new):
  """Rename old to new in repo"""
  with temp_chdir(repo):
    return subprocess.check_output(
        ['git', 'mv', old, new])


def git_file_lastlog(repo, filepath):
  """Return a string containing the short hash, date, author email, and title
  of most recent commit of filepath, separated by tab."""
  with temp_chdir(repo):
    return subprocess.check_output(
        ['git', 'log', '-n', '1', '--format=%h\t%ad\t%ae\t%s', '--date=short',
         '--', filepath])


def git_tags(repo):
  """Return a list of info about annotated tags.  The list consists of tuples
  of the commit hash (as a string), the  tag name, and the time, sorted in
  in reverse chronological order (most recent first).  The hash is for the
  referenced commit and not the tag itself, but the date is the tag date."""
  with temp_chdir(repo):
    text = subprocess.check_output([
        'git', 'tag', '-l',
        '--format=%(*objectname)|%(refname:strip=2)|'
        '%(taggerdate:format:%Y-%m-%d %T %Z)',
        '--sort=-taggerdate'])
    return [tuple(line.split('|')) for line in text.splitlines()
            if not line.strip().startswith('|')]


def git_tag_info(repo, tag_name):
  """Return the annotation for this tag in the repo.  It is limited to no more
  than 50 lines."""
  # Unfortunately, I can't get the other formatted tag info and also limit
  # to the tag annotation without more serious munging of tag or show output.
  with temp_chdir(repo):
    text = subprocess.check_output(['git', 'tag', '-l', '-n50', tag_name])
    lines = text[len(tag_name):].strip().splitlines()
    return '\n'.join(l.strip() for l in lines)


def get_tool_generated(repo, subdir, commit_title_prefix='Updated by tool'):
  """
  Return a list of the names of tool-generated files in the provided directory.
  The idea is that when we check in files that are generated by a tool, the
  commit will start with the given prefix.  If a files' most recent log entry
  matches this, it means that we've not applied patches or fixes to the file
  since it was generated, so we can overwrite it with new tool-generated data.

  The motivation for this is mantaining the sample texts.  The original source
  for most of these is UDHR data, but subsequently we have fixed things in
  some of the samples.  We generally do not want to blindly overwrite these
  fixes, but do want to be able to regenerate the samples if we get new source
  data.
  """
  files_not_under_version_control = [];
  protected_files = []
  tool_generated_files = []
  for f in sorted(os.listdir(path.join(repo, subdir))):
    relpath = path.join(subdir, f)
    lastlog_str = git_file_lastlog(repo, relpath)
    if not lastlog_str:
      files_not_under_version_control.append(f)
      continue
    commit, date, author, title = lastlog_str.split('\t')
    if title.startswith(commit_title_prefix):
      tool_generated_files.append(f)
    else:
      protected_files.append(f)

  if files_not_under_version_control:
    print >> sys.stderr, '%d files were not under version control:\n  %s' % (
        len(files_not_under_version_control),
        ', '.join(files_not_under_version_control))

  if protected_files:
    print >> sys.stderr, '%d files protected:\n  %s' % (
        len(protected_files), ', '.join(protected_files))

  return tool_generated_files


def git_get_branch(repo):
  try:
    with temp_chdir(repo):
      with open(os.devnull) as trash:
        return subprocess.check_output(
            ['git', 'symbolic-ref', '--short', 'HEAD'], stderr=trash).strip()
  except:
    return '<not on any branch>'


def git_is_clean(repo, print_errors=False):
  """Ensure there are no unstaged or uncommitted changes in the repo."""

  def capture_and_show_errors(cmd):
    def dumplines(msg, text, limit):
      if text:
        lines = text.splitlines()
        print '%s (%d lines):\n  %s' % (
            msg, len(lines), '\n  '.join(lines[:limit]))
        if len(lines) > limit:
          print '  ...'

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    dumplines('out', out, 20)
    dumplines('err', err, 20)

  result = True
  with temp_chdir(repo):
    subprocess.check_call(
        ['git', 'update-index', '-q', '--ignore-submodules', '--refresh'])
    if subprocess.call(
        ['git', 'diff-files', '--quiet', '--ignore-submodules', '--']):
      if (print_errors):
        print 'There are unstaged changes:'
        capture_and_show_errors(
            ['git', 'diff-files', '--name-status', '-r', '--ignore-submodules',
             '--'])
      result = False
    if subprocess.call(
        ['git', 'diff-index', '--cached', '--quiet', 'HEAD',
         '--ignore-submodules', '--']):
      if (print_errors):
        print 'There are uncommitted changes:'
        capture_and_show_errors(
            ['git', 'diff-index', '--cached', '--name-status', '-r', 'HEAD',
             '--ignore-submodules', '--'])
      result = False
  return result


def git_head_commit(repo):
  """Return the commit hash at head, the date and time of the commit as
  YYYY-mm-dd HH:MM:SS, and the subject line, as a tuple of three strings."""
  with temp_chdir(repo):
    text = subprocess.check_output(
        ['git', 'show', '-s', '--date=format:%Y-%m-%d %H:%M:%S',
         '--no-expand-tabs', '--pretty=format:%H\t%cd\t%s', 'HEAD'])
    return tuple(text.strip().split('\t', 2))


def git_check_remote_commit(repo, commit, remote='upstream', branch='master'):
  """Return true if the commit exists in the remote repo at the given branch
  (or any branch if branch is None). This has the side effect of calling
  'git fetch {remote}'."""
  with temp_chdir(repo):
    subprocess.check_call(['git', 'fetch', remote])
    # the following will throw an exception if commit is unrecognized
    text = subprocess.check_output(
          ['git', 'branch', '-r', '--contains', commit])

    lines = [line.strip() for line in text.splitlines()]
    if branch:
      if branch == 'HEAD':
        # assume a link, it will be reported as one
        expected = remote + '/HEAD ->'
        return any(line.startswith(expected) for line in lines)
      expected = remote + '/' + branch
      return expected in lines
    else:
      expected = remote + '/'
      return any(line.startswith(remote) for line in lines)


def git_add_all(repo_subdir):
  """Add all changed, deleted, and new files in subdir to the staging area."""
  # git can now add everything, even removed files
  with temp_chdir(repo_subdir):
    subprocess.check_call(['git', 'add', '--', '.'])


def svn_get_version(repo):
  with temp_chdir(repo):
    version_string = subprocess.check_output(['svnversion', '-c']).strip()
    colon_index = version_string.find(':')
    if colon_index >= 0:
      version_string = version_string[colon_index + 1:]
  return version_string


def svn_update(repo):
  with temp_chdir(repo):
    subprocess.check_call(['svn', 'up'], stderr=subprocess.STDOUT)


def parse_int_ranges(
    range_string, is_hex=True, sep=None, allow_duplicates=False,
    return_set=True, allow_compressed=False):
  """Returns a set/list of ints from a string of numbers or ranges separated by
  sep.  A range is two values separated by hyphen with no intervening separator;
  ranges are inclusive.  If allow_compressed is true, '/' is also allowed
  as a separator, and ranges following it or hyphen are interpreted as suffixes
  that replace the same number of characters at the end of the previous value.
  '-' generates the range of intervening characters as before, while '/' does
  not.  Returns a set or a list depending on return_set.

  For example, with compressed ranges the following:
    1ee42/7/9/b/d-f 1ee51-2/4/7/9/b/d/f

  expands to:
    1ee42 1ee47 1ee49 1ee4b 1ee4d-1ee4f 1ee51-1ee52 1ee54 1ee57 1ee59 1ee5b
    1ee5d 1ee5f
  """

  base = 16 if is_hex else 10
  vals = []

  def _add_segment(prev_str, suffix, is_range):
    slen = len(suffix)
    if prev_str == None:
      next_str = suffix
      next_val = int(next_str, base)
    else:
      if slen > len(prev_str):
        raise ValueError(
            'suffix \'%s\' is longer than previous \'%s\'' % (suffix, prev_str))
      next_str = prev_str[:-slen] + suffix

      next_val = int(next_str, base)
      if next_val <= vals[-1]:
        raise ValueError(
            'next value \'%s\' is not greater than previous \'%s\'' % (
                next_str, prev_str))

    if is_range:
      start_val = vals[-1] + 1
      vals.extend(range(start_val, next_val))
    vals.append(next_val)

    return next_str

  def _add_range(r):
    stops = '-/'
    if len(r) == 0:
      raise ValueError('empty range')
    if r[0] in stops:
      raise ValueError('range "%s" has leading separator' % r)
    if r[-1] in stops:
      raise ValueError('range "%s" has trailing separator' % r)
    r = r + '/'

    prev_str = None
    is_range = False
    start = 0
    len_limit = -1
    for i in xrange(len(r)):
      cp = r[i]
      if cp not in stops:
        continue

      if i == start:
        raise ValueError('range "%s" has two separators together' % r)

      if is_range and cp == '-':
        raise ValueError('range "%s" has two \'-\' in sequence' % r)

      if not allow_compressed:
        if start == 0:
          len_limit = i
        elif i - start > len_limit:
          raise ValueError(
              'segment \'%s\' longer than previous segment' % r[start: i])
        else:
          len_limit = i - start

      prev_str = _add_segment(prev_str, r[start: i], is_range)
      is_range = cp == '-'
      start = i + 1

  # main
  # handle comments and multiline input
  if '\n' in range_string or '#' in range_string:
    # strip comments and turn into single line
    def strip_comment(line):
      x = line.find('#')
      if x >= 0:
        line = line[:x]
      return line.strip()
    join_char = ' ' if sep == None else sep
    range_string = join_char.join(
        filter(
            None,
            (strip_comment(line) for line in range_string.splitlines())))

  if not allow_compressed and '/' != sep and range_string.find('/') != -1:
    raise ValueError('\'/\' only allowed in compressed range format')

  # collect ordered list of values
  for r in range_string.split(sep):
    _add_range(r)

  # check for duplicates and/or convert to set
  if return_set or not allow_duplicates:
    range_set = set(vals)
    if not allow_duplicates and len(range_set) != len(vals):
      fail = set()
      seen = set()
      for v in vals:
        if v in seen:
          fail.add(v)
        else:
          seen.add(v)
      raise ValueError('range "%s" has %d duplicates: %s' % (
          range_string, len(fail), write_int_ranges(fail)))

  return range_set if return_set else vals


def write_int_ranges(int_values, in_hex=True, sep=' '):
  """From a set or list of ints, generate a string representation that can be
  parsed by parse_int_ranges to return the original values (not
  order_preserving)."""

  if not int_values:
    return ''

  num_list = []

  if type(int_values) is not list:
    int_values = [v for v in int_values]
  int_values.sort()
  start = prev = int_values[0]
  single_fmt = '%04x' if in_hex else '%d'
  pair_fmt = single_fmt + '-' + single_fmt

  def emit():
    if prev == start:
      num_list.append(single_fmt % prev)
    else:
      num_list.append(pair_fmt % (start, prev))

  for v in int_values[1:]:
    if v == prev + 1:
      prev += 1
      continue
    else:
      emit()
    start = prev = v
  emit()
  return sep.join(num_list)


def setup_logging(loglevel, quiet_ttx=True):
  """Set up logging to stream to stdout.

  The loglevel is a logging level name or a level value (int or string).

  ttx/fontTools uses 'info' to report when it is reading/writing tables,
  but when we want 'info' in our own tools we usually don't want this detail.
  When quiet_ttx is true, set up logging to treat 'info' logs from
  fontTools misc.xmlReader and ttLib as though they were at level 19."""

  try:
    loglevel = int(loglevel)
  except:
    loglevel = getattr(logging, loglevel.upper(), loglevel)
  if not isinstance(loglevel, int):
    print ('Could not set log level, should be one of debug, info, warning, '
           'error, critical, or a numeric value')
    return
  logging.basicConfig(level=loglevel)

  if quiet_ttx and loglevel == logging.INFO:
    for logger_name in ['fontTools.misc.xmlReader', 'fontTools.ttLib']:
      logger = logging.getLogger(logger_name)
      logger.setLevel(loglevel + 1)


def write_lines(lines, outfile):
  """Write lines as utf-8 to outfile, separated by and ending with newline"""
  ensure_dir_exists(path.dirname(outfile))
  with codecs.open(outfile, 'w', 'utf-8') as f:
    f.write('\n'.join(lines + ['']))


def read_lines(infile, ignore_comments=True, strip=True, skip_empty=True):
  """Read lines from infile and return as a list, optionally stripping comments,
  whitespace, and/or skipping blank lines."""
  lines = []
  with codecs.open(infile, 'r', 'utf-8') as f:
    for line in f:
      if ignore_comments:
        ix = line.find('#')
        if ix >= 0:
          line = line[:ix]
      if strip:
        line = line.strip()
      if not line and skip_empty:
        continue
      lines.append(line)
  return lines


def _read_filename_list(filenames):
  with open(filenames, 'r') as f:
    return [resolve_path(n.strip()) for n in f if n]


# see noto_fonts.NOTO_FONT_PATHS
NOTO_FONT_PATHS = [
    '[fonts]/hinted', '[fonts]/unhinted', '[emoji]/fonts', '[cjk]']


def collect_paths(dirs, files):
  """Return a collection of all files in any of the listed dirs, and
  the listed files.  Can use noto short paths.  A file name starting
  with '@' is interpreted as the name of a file containing a list
  of filenames one per line.  The short name '[noto]' refers to
  the noto (phase 2) font paths."""

  paths = []
  if dirs:
    for i in xrange(len(dirs)):
      # special case '[noto]' to include all noto font dirs
      if dirs[i] == '[noto]':
        dirs[i] = None
        dirs.extend(NOTO_FONT_PATHS)
        dirs = filter(None, args.dirs)
        break
    for d in dirs:
      d = resolve_path(d)
      paths.extend(n for n in glob.glob(path.join(d, '*')))
  if files:
    for fname in files:
      if fname[0] == '@':
        paths.extend(_read_filename_list(fname[1:]))
      else:
        paths.append(resolve_path(fname))
  return paths
