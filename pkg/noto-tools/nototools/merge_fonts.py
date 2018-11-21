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

"""Merges fonts.
Two notable differences between merge_noto and this script are:
1. merge_noto merges all fonts in Noto, or merges a subset of Noto
   clustered by region. While This script merges a selected font subset.
2. The line metrics in the final merged font are substituted by those in
   NotoSans-Regular.ttf (LGC). This is to optimize the user experience in LGC.
   The drawback is some tall scripts in the file list (like Balinese, Cuneiform,
  Javaness) might vertically overlap with each other and also be clipped by the
  edge of the UI. This should be handled carefully by the UI designer, say
  changing the line height or adding the margin.


Sample Usage:
    $ merge_fonts.py -d noto-fonts/unhinted -o NotoSansMerged-Regular.ttf

"""
import sys
import os.path
import logging
from argparse import ArgumentParser

from fontTools import ttLib
from fontTools import merge
from merge_noto import add_gsub_to_font, has_gsub_table
from nototools.substitute_linemetrics import read_line_metrics, set_line_metrics
from fontTools.misc.loggingTools import Timer

log = logging.getLogger("nototools.merge_fonts")


# directory that contains the files to be merged
directory = ''


# file names to be merged
files = [
    # It's recommended to put NotoSans-Regular.ttf as the first element in the
    # list to maximize the amount of meta data retained in the final merged font.
    'NotoSans-Regular.ttf',
    'NotoSansAvestan-Regular.ttf',
    'NotoSansBalinese-Regular.ttf',
    'NotoSansBamum-Regular.ttf',
    'NotoSansBatak-Regular.ttf',
    'NotoSansBrahmi-Regular.ttf',
    'NotoSansBuginese-Regular.ttf',
    'NotoSansBuhid-Regular.ttf',
    'NotoSansCarian-Regular.ttf',
    'NotoSansCoptic-Regular.ttf',
    'NotoSansCuneiform-Regular.ttf',
    'NotoSansCypriot-Regular.ttf',
    'NotoSansEgyptianHieroglyphs-Regular.ttf',
    'NotoSansGlagolitic-Regular.ttf',
    'NotoSansGothic-Regular.ttf',
    'NotoSansHanunoo-Regular.ttf',
    'NotoSansImperialAramaic-Regular.ttf',
    'NotoSansInscriptionalPahlavi-Regular.ttf',
    'NotoSansInscriptionalParthian-Regular.ttf',
    'NotoSansJavanese-Regular.ttf',
    'NotoSansKaithi-Regular.ttf',
    'NotoSansKayahLi-Regular.ttf',
    'NotoSansKharoshthi-Regular.ttf',
    'NotoSansLepcha-Regular.ttf',
    'NotoSansLimbu-Regular.ttf',
    'NotoSansLinearB-Regular.ttf',
    'NotoSansLisu-Regular.ttf',
    'NotoSansLycian-Regular.ttf',
    'NotoSansLydian-Regular.ttf',
    'NotoSansMandaic-Regular.ttf',
    'NotoSansMeeteiMayek-Regular.ttf',
    'NotoSansMongolian-Regular.ttf',
    'NotoSansNKo-Regular.ttf',
    'NotoSansNewTaiLue-Regular.ttf',
    'NotoSansOgham-Regular.ttf',
    'NotoSansOlChiki-Regular.ttf',
    'NotoSansOldItalic-Regular.ttf',
    'NotoSansOldPersian-Regular.ttf',
    'NotoSansOldSouthArabian-Regular.ttf',
    'NotoSansOldTurkic-Regular.ttf',
    'NotoSansOsmanya-Regular.ttf',
    'NotoSansPhagsPa-Regular.ttf',
    'NotoSansPhoenician-Regular.ttf',
    'NotoSansRejang-Regular.ttf',
    'NotoSansRunic-Regular.ttf',
    'NotoSansSamaritan-Regular.ttf',
    'NotoSansSaurashtra-Regular.ttf',
    'NotoSansShavian-Regular.ttf',
    'NotoSansSundanese-Regular.ttf',
    'NotoSansSylotiNagri-Regular.ttf',
    'NotoSansSyriacEastern-Regular.ttf',
    'NotoSansTagalog-Regular.ttf',
    'NotoSansTagbanwa-Regular.ttf',
    'NotoSansTaiLe-Regular.ttf',
    'NotoSansTaiTham-Regular.ttf',
    'NotoSansTaiViet-Regular.ttf',
    'NotoSansThaana-Regular.ttf',
    'NotoSansTifinagh-Regular.ttf',
    'NotoSansUgaritic-Regular.ttf',
    'NotoSansVai-Regular.ttf',
    'NotoSansYi-Regular.ttf',
    'NotoSansCham-Regular.ttf',
]


def build_valid_filenames(files=files, directory=directory):
    files = list(files)
    directory = directory.rstrip('/')
    if directory == '' or directory == None:
        directory = '.'
    valid_files = []
    for f in files:
        valid_file = directory + '/' + f
        if not os.path.isfile(valid_file):
            log.warn('can not find %s, skipping it.' % valid_file)
        else:
            valid_files.append(valid_file)

    if len(valid_files) == 0:
        return valid_files
    if os.path.basename(valid_files[0]) != files[0]:
        log.warn('can not find the font %s to read line metrics from. Line '
            + 'metrics in the result might be wrong.' % files[0])
    return valid_files


def main():
    t = Timer()
    parser = ArgumentParser()
    parser.add_argument('-d', '--directory', default='./',
        help='Path to directory containing the fonts')
    parser.add_argument('-o', '--output', default='merged.ttf',
        help='Path to output file.')
    parser.add_argument('-v', '--verbose', action='store_true',
        help='Verbose mode, printing out more info')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    valid_files = build_valid_filenames(directory=args.directory)
    if len(valid_files) <= 1:
        log.warn('expecting at least two fonts to merge, but only got %d '
            + 'font(s).', len(valid_files))
        sys.exit(-1)

    for idx, file in enumerate(valid_files):
        if not has_gsub_table(file):
            log.info('adding default GSUB table to %s.' % file)
            valid_files[idx] = add_gsub_to_font(file)

    merger = merge.Merger()
    print('Merging %d Fonts...' % len(valid_files))
    font = merger.merge(valid_files)
    # Use the line metric in the first font to replace the one in final result.
    metrics = read_line_metrics(ttLib.TTFont(valid_files[0]))
    set_line_metrics(font, metrics)
    font.save(args.output)
    font.close()

    print('%d fonts are merged. %d fonts are skipped. Cost %0.3f s.' % (len(valid_files), len(files) - len(valid_files), t.time()))
    print('Please check the result at %s.' % os.path.abspath(
        os.path.realpath(args.output)))


if __name__ == '__main__':
    main()
