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
"""Finds potential problems in Noto fonts."""

__author__ = (
    "roozbeh@google.com (Roozbeh Pournader), "
    "cibu@google.com (Cibu Johny), "
    "behdad@google.com (Behdad Esfahbod), and "
    "stuartg@google.com (Stuart Gill)")


import argparse
import collections
import itertools
import json
import math
import os
from os import path
import re
import subprocess
import sys
import tempfile

from fontTools import subset
from fontTools import ttLib
from fontTools.ttLib.tables import otTables
from fontTools.misc import arrayTools
from fontTools.misc import bezierTools
from fontTools.pens import basePen

from nototools import cldr_data
from nototools import cmap_data
from nototools import font_data
from nototools import lint_config
from nototools import notoconfig
from nototools import noto_data
from nototools import noto_fonts
from nototools import noto_names
from nototools import opentype_data
from nototools import render
from nototools import tool_utils
from nototools import unicode_data

# from wikipedia windows 1252 page.  As of windows 98.
WIN_ANSI_CODEPOINTS = (
    '0000-007f 00A0-00ff 20ac 201a 0192 201e 2026 2020 2021 02c6 2030 0160 2039 0152 017d'
    '2018 2019 201c 201d 2022 2013 2014 02dc 2122 0161 203a 0153 017e 0178')

def all_scripts():
    """Extends unicode scripts with pseudo-script 'Urdu'."""
    result = set(unicode_data.all_scripts())
    result.add('Urdu')
    return frozenset(result)


def printable_unicode_range(input_char_set):
    char_set = set(input_char_set) # copy
    parts_list = []
    while char_set:
        last = first = min(char_set)
        while last in char_set:
            char_set.remove(last)
            last += 1
        if last == first + 1:
            part = "%04X" % first
        else:
            part = "%04X..%04X" % (first, last-1)
        parts_list.append(part)
    return ", ".join(parts_list)


def next_circular_point(current_point, start_of_range, end_of_range):
    if current_point == end_of_range:
        return start_of_range
    else:
        return current_point + 1


def curve_between(
    coordinates, start_at, end_at, start_of_contour, end_of_contour):
    """Returns indices of a part of a contour between start and end of a curve.

    The contour is the cycle between start_of_contour and end_of_contour,
    and start_at and end_at are on-curve points, and the return value
    is the part of the curve between them.
    Args:
      coordinates: An slicable object containing the data.
      start_at: The index of on-curve beginning of the range.
      end_at: The index of on-curve end of the range.
      start_of_contour: The index of beginning point of the contour.
      end_of_contour: The index of ending point of the contour.
    Returns:
      A list of coordinates, including both start_at and end_at. Will go around
      the contour if necessary.
    """
    if end_at > start_at:
        return list(coordinates[start_at:end_at+1])
    elif start_of_contour == end_of_contour:  # single-point contour
        assert start_at == end_at == start_of_contour
        return [coordinates[start_at]]
    else:  # the curve goes around the range
        return (list(coordinates[start_at:end_of_contour+1]) +
                list(coordinates[start_of_contour:end_at+1]))


def curve_has_off_curve_extrema(curve):
    """Checks if a curve has off-curve extrema.

    Args:
      curve: a list of coordinates for the curve, where the first and the last
        coordinates are on-curve points, and the rest are off-curve.
    Returns:
      A boolean value, True if there are off-curve extrema,
      False if there are none.
    """
    if len(curve) <= 2:  # It's a straight line
        return False

    angles = []
    prev_x, prev_y = curve[0]
    for curr_x, curr_y in curve[1:]:
        angle = math.atan2(curr_y - prev_y, curr_x - prev_x)
        angles.append(angle)
        prev_x, prev_y = curr_x, curr_y

    # For the curve to have no local extrema, the angles must all fall in the
    # same quartet of the plane (e.g. all being between pi/2 and pi).
    #
    # There's a painful edge case, where an angle is equal to pi, and is
    # acceptable as both +pi and -pi for the logic that comes after. But since
    # the return value of math.atan2 is always in (-pi, +pi], we'll miss the -pi
    # case, resulting in false positives.
    #
    # For these cases, we check for the curve being proper once with all of
    # these set to +pi and then with all set to -pi. If the curve is proper in
    # at least one case, we assume the curve has no missing extrema.

    ninety_deg = math.pi/2
    score = 0
    for sign in [-1, +1]:
        angles = [sign*math.pi if math.fabs(angle) == math.pi else angle
                  for angle in angles]
        min_quarter = math.floor(min(angles) / ninety_deg)
        max_quarter = math.ceil(max(angles) / ninety_deg)
        if math.fabs(max_quarter - min_quarter) > ninety_deg:
            score += 1

    if score == 2:  # The curve failed the test in both cases
        return out_of_box_size(curve)

    return 0

# Finds out the how far away the off-curve extrema lies from the on-curve
# points. This is done by comparing the bounding box of the endpoints with that
# of the bezier curve. If there are implicit on-curve points, the curve is
# split up into a sequence of simple 3-point curves by inserting those implicit
# points.
def out_of_box_size(curve):
    if len(curve) < 3:
        return 0

    if len(curve) > 3:
        # If curve has more than 3 points, then it has implicit on-curve points.
        # First two off-curve points.
        ax, ay = curve[1]
        bx, by = curve[2]
        # Implicit point is the mid point of first two off-curve points.
        implicit_point = ((ax + bx)/2, (ay + by)/2)
        first_curve = curve[:2] + [implicit_point]
        remaining_curve = [implicit_point] + curve[2:]
    else:
        # Curve with exact 3 points has no implicit on-curve point.
        first_curve = curve
        remaining_curve = []

    # Endpoints of the first curve.
    ax, ay = first_curve[0]
    bx, by = first_curve[-1]
    # Bounding box for just the endpoints.
    ex1, ey1, ex2, ey2 = min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)
    # Bounding box for the bezier curve.
    bx1, by1, bx2, by2 = bezierTools.calcQuadraticBounds(*first_curve)

    # Bounding box of the bezier will contain that of the endpoints.
    # The out-of-box size for the entire curve will be maximum of the deviation
    # for the first curve and that of the remaining curve.
    delta = max(ex1 - bx1, ey1 - by1, bx2 - ex2, by2 - ey2,
               out_of_box_size(remaining_curve))
    # ignore very small deviations
    return 0 if delta < 1 else delta


def calc_bounds(piece):
    if len(piece) == 2:
        return arrayTools.normRect(piece[0] + piece[1])
    else:
        return bezierTools.calcQuadraticBounds(piece[0], piece[1], piece[2])


def interpolate(start, end, amount):
    return start + amount * (end - start)


def interpolate_segment(segment, amount):
    return (interpolate(segment[0][0], segment[1][0], amount),
            interpolate(segment[0][1], segment[1][1], amount))


def cut_piece_in_half(piece):
    if len(piece) == 2:
        mid_point = interpolate_segment(piece, 0.5)
        return (piece[0], mid_point), (mid_point, piece[1])
    else:
        return bezierTools.splitQuadraticAtT(
            piece[0], piece[1], piece[2],
            0.5)

def cut_ends(piece, cut_amount):
    if len(piece) == 2:
        return (interpolate_segment(piece, cut_amount),
                interpolate_segment(piece, 1 - cut_amount))
    else:
        return bezierTools.splitQuadraticAtT(
            piece[0], piece[1], piece[2],
            cut_amount, 1 - cut_amount)[1]


def probably_intersect(piece1, piece2):
    bounds1 = calc_bounds(piece1)
    bounds2 = calc_bounds(piece2)
    return arrayTools.sectRect(bounds1, bounds2)[0]


_EPSILON = 1.0/(2**14)
_MAX_DEPTH = 30

def curve_pieces_intersect(piece1, piece2, ignore_ends):
    if ignore_ends:
        piece1 = cut_ends(piece1, _EPSILON)
        piece2 = cut_ends(piece2, _EPSILON)

    # If we are not ignoring end points, let's quickly check for end point
    # collision
    if not ignore_ends and {piece1[0], piece1[-1]} & {piece2[0], piece2[-1]}:
        return True

    pairs_to_investigate = collections.deque()
    if probably_intersect(piece1, piece2):
        pairs_to_investigate.append((piece1, piece2, 0))

    while True:
        if not pairs_to_investigate:
            return False
        section1, section2, level = pairs_to_investigate.popleft()
        section11, section12 = cut_piece_in_half(section1)
        section21, section22 = cut_piece_in_half(section2)
        for first_section in [section11, section12]:
            for second_section in [section21, section22]:
                if probably_intersect(first_section, second_section):
                    if level > _MAX_DEPTH:
                        return True
                    else:
                        pairs_to_investigate.append(
                            (first_section, second_section, level+1))

def to_float_tuples(curve):
    coord_list = []
    for coords in curve:
        coord_list.append(
            (float(coords[0]), float(coords[1]))
        )
    return tuple(coord_list)


def curves_intersect(contour_list):
    """Takes a list of contours and tells if any two curves in them intersect.
    Returns a message string with an error, or None if ok.
    """
    all_contours = []
    for contour in contour_list:
        contour_pieces = []
        for curve in contour:
            if len(curve) == 2:
                contour_pieces.append(to_float_tuples(curve))
            elif len(curve) > 2:
                last_point = curve[0]
                for curve_part in basePen.decomposeQuadraticSegment(curve[1:]):
                    contour_pieces.append(
                        to_float_tuples((last_point,) + curve_part))
                    last_point = curve_part[1]
        all_contours.append(contour_pieces)

    for contour_pieces in all_contours:
        for piece in contour_pieces:
            if piece[0] == piece[-1]:
                return 'start and end segments match: %s' % str(piece[0])

    all_pieces = sum(all_contours, [])
    if len(set(all_pieces)) != len(all_pieces):
        print 'some pieces are duplicates' # No piece should be repeated

    adjacent_pairs = set()
    for contour_pieces in all_contours:
        for i in range(len(contour_pieces)-1):
            adjacent_pairs.add(
                frozenset({contour_pieces[i], contour_pieces[i+1]}))
        if len(contour_pieces) > 2:
            adjacent_pairs.add(
                frozenset({contour_pieces[-1], contour_pieces[0]}))

    for piece1, piece2 in itertools.combinations(all_pieces, 2):
        # FIXME(roozbeh): we are ignoring one edge case: where end points
        # of the wrong side of an adjacent pair overlap. For example, if
        # a contour curves from A to B, then immediately back to A, and then
        # on to C, we won't catch it.
        ok_to_intersect_at_ends = frozenset({piece1, piece2}) in adjacent_pairs
        if curve_pieces_intersect(piece1, piece2, ok_to_intersect_at_ends):
            return 'intersection %s and %s' % (piece1, piece2)

    return None


def font_version(font):
    return font_data.get_name_records(font)[5]


def printable_font_revision(font, accuracy=2):
    font_revision = font["head"].fontRevision
    font_revision_int = int(font_revision)
    font_revision_frac = int(
        round((font_revision - font_revision_int) * 10**accuracy))

    font_revision_int = str(font_revision_int)
    font_revision_frac = str(font_revision_frac).zfill(accuracy)
    return font_revision_int+"."+font_revision_frac


def printable_font_versions(font):
    version = font_version(font)
    match = re.match(r"Version (\d{1,5})\.(\d{1,5})", version)
    if match:
        major_version = match.group(1)
        minor_version = match.group(2)
        accuracy = len(minor_version)
        font_revision = printable_font_revision(font, accuracy)
        if font_revision == major_version+"."+minor_version:
            return version
    else:
        font_revision = printable_font_revision(font, 3)
    return "%s (head fontRevision: %s)" % (
        version, font_revision)


def _build_cmap_dict(filename):
    filename = tool_utils.resolve_path(filename)
    data = cmap_data.read_cmap_data_file(filename)
    script_to_rowdata = cmap_data.create_map_from_table(data.table)
    return {script: frozenset(tool_utils.parse_int_ranges(rd.ranges))
            for script, rd in script_to_rowdata.iteritems()}


_phase_2_map = None
_phase_3_map = None
def _get_cmap_data_for_phase(phase):
    global _phase_2_map, _phase_3_map
    if phase < 3:
        if not _phase_2_map:
            _phase_2_map = _build_cmap_dict(
                '[tools]/nototools/data/noto_cmap_phase2.xml')
        return _phase_2_map
    else:
        if not _phase_3_map:
            _phase_3_map = _build_cmap_dict(
                '[tools]/nototools/data/noto_cmap_phase3.xml')
        return _phase_3_map


HARD_CODED_FONT_INFO = {
    "AndroidEmoji.ttf": ("Sans", "Zsye", None, "Regular"),
    "DroidEmoji.ttf": ("Sans", "Zsye", None, "Regular"),
    "NotoEmoji-Regular.ttf": ("", "Zsye", None, "Regular"),
    "NotoNaskh-Regular.ttf": ("Naskh", "Arab", None, "Regular"),
    "NotoNaskh-Bold.ttf": ("Naskh", "Arab", None, "Bold"),
    "NotoNaskhUI-Regular.ttf": ("Naskh", "Arab", "UI", "Regular"),
    "NotoNaskhUI-Bold.ttf": ("Naskh", "Arab", "UI", "Bold"),
    "NotoSansCypriotSyllabary-Regular.ttf": ("Sans", "Cprt", None, "Regular"),
    "NotoSansEmoji-Regular.ttf": ("Sans", "Zsye", None, "Regular"),
    "NotoSansKufiArabic-Regular.ttf": ("Kufi", "Arab", None, "Regular"),
    "NotoSansKufiArabic-Bold.ttf": ("Kufi", "Arab", None, "Bold"),
    "NotoSansSymbols-Regular.ttf": ("Sans", "Zsym", None, "Regular"),
    "NotoNastaliqUrduDraft.ttf": ("Nastaliq", "Urdu", None, "Regular"),
    "NotoNastaliq-Regular.ttf": ("Nastaliq", "Urdu", None, "Regular")
}

# these are based on a upem of 2048
MAX_UI_HEIGHT = 2163
MIN_UI_HEIGHT = -555
UI_ASCENT = 2189
UI_DESCENT = -600


_cur_file_name = None
_printed_file_name = False
_processed_files = 0
_processed_files_with_errors = 0
_processed_files_with_warnings = 0

FontProps = collections.namedtuple(
    'FontProps',
    'is_google, vendor, char_version, '
    'filepath, family, style, script, variant, width, weight, slope, fmt, '
    'manufacturer, license_type, is_hinted, is_mono, is_UI, is_UI_metrics, '
    'is_display, is_cjk, subset')


def font_properties_from_name(file_path, phase):
    noto_font = noto_fonts.get_noto_font(file_path, phase=phase)
    if not noto_font:
        return None

    is_google = True
    vendor = ('Adobe' if noto_font.is_cjk
              else 'KhmerType' if noto_font.script in ['Khmr', 'Cham', 'Laoo']
              else 'Monotype')

    char_version = 6.0 if noto_font.family == 'Noto' else 8.0
    return FontProps(is_google, vendor, char_version, *noto_font)


def get_font_properties_with_fallback(file_path, phase):
    props = font_properties_from_name(file_path, phase)
    if props:
        return props, '' if props.script else 'script'

    basename = path.basename(file_path)
    if not basename in HARD_CODED_FONT_INFO:
        return None, None

    style, script, ui, weight = HARD_CODED_FONT_INFO[basename]
    return FontProps(
        True, 'Monotype', 6.0,
        file_path, 'Noto', style, script, '', weight, None, 'ttf', 'sil',
        False, False, bool(ui), bool(ui), False, ''), 'name'


def check_font(font_props, filename_error,
               lint_spec, runlog=False, skiplog=False,
               csv_flag=False, info_flag=False,
               extrema_details=True, nowarn=False,
               quiet=False, noto_phase=3, variable=False):
    global _processed_files

    _processed_files += 1

    def _noto_font_from_font_props(font_props):
      fields = """
          filepath,family,style,script,variant,width,weight,slope,fmt,
          manufacturer,license_type,is_hinted,is_mono,is_UI,is_UI_metrics,
          is_display,is_cjk,subset
      """.split(',')
      vals = [getattr(font_props, p.strip()) for p in fields]
      return noto_fonts.NotoFont(*vals)

    noto_font = _noto_font_from_font_props(font_props)

    def warn(test_name, category_name, message, details=True, is_error=True, check_test=True):
        global _cur_file_name, _printed_file_name
        global _processed_files_with_errors, _processed_files_with_warnings

        def print_file_name():
            global _printed_file_name
            if not _printed_file_name:
                _printed_file_name = True
                print "---\nAutomatic testing for '%s', %s:" % (
                    _cur_file_name,
                    printable_font_versions(font))

        if check_test and not tests.check(test_name):
          return

        interesting_part_of_file_name = ",".join(font_props.filepath.split("/")[-2:])
        if interesting_part_of_file_name != _cur_file_name:
            _cur_file_name = interesting_part_of_file_name
            _printed_file_name = False

        # Assumes "info" only and always comes at the end of
        # processing a file.
        if category_name is "info":
            def pluralize_errmsg(count, is_error=True):
                msg = "error" if is_error else "warning"
                if count == 0:
                    return "no %ss" % msg
                elif count == 1:
                    return "1 " + msg
                else:
                    return "%d %ss" % (count, msg)

            ec = err_count[0]
            wc = warn_count[0]
            if not csv_flag and (not quiet or ec or (wc and not nowarn)):
                print_file_name()
                se = suppressed_err_count[0]
                if not se:
                    print "Found %s." % pluralize_errmsg(ec)
                else:
                    print "Found %s (%s hidden)." % (pluralize_errmsg(ec),
                                                     "all" if se == ec else se)
                if wc and not nowarn:
                    sw = suppressed_warn_count[0]
                    if not sw and wc:
                        print "Found %s." % pluralize_errmsg(wc, False)
                    elif wc:
                        print "Found %s (%s hidden)." % (pluralize_errmsg(wc, False),
                                                         "all" if sw == wc else sw)

            if ec:
                _processed_files_with_errors += 1
            elif wc:
                _processed_files_with_warnings += 1

            if not info_flag:
                return

        if is_error:
            err_count[0] += 1
        else:
            warn_count[0] += 1

        if is_error:
            if not details:
                suppressed_err_count[0] += 1
        else:
            if nowarn or not details:
                suppressed_warn_count[0] += 1

        if not details:
            return

        if nowarn and not is_error:
            return

        if not csv_flag:
            print_file_name()

        err_type = 'Info' if category_name is "info" else "Error" if is_error else "Warning"
        if csv_flag:
            names = []
            if font_props.weight != 'Regular' or not font_props.slope:
                names.append(font_props.weight)
            if font_props.slope:
                names.append(font_props.slope)
            subfamily = ''.join(names)
            print ('%s,%s,%s,%s,%s,%s,%s,%s,%s,"%s"' % (
                err_type,
                noto_fonts.script_name_for_report(font_props.script),
                font_props.style if font_props.style else '',
                font_props.variant if font_props.variant else '',
                subfamily,
                font_data.get_name_records(font)[8].split()[0],
                category_name,
                interesting_part_of_file_name,
                printable_font_revision(font),
                message)).encode('UTF-8')
        else:
            print "%s <%s> %s" % (err_type[0], test_name, message.encode('UTF-8'))
        sys.stdout.flush()


    _script_key_to_font_name = {
        'Aran': 'Urdu',
        'HST': 'Historic',
        'LGC': None,
        'Zsye': None,
    }


    def _check_unused_names():
      # For now, just a warning, and we don't actually check if other tables use it.
      # Add those checks as we need them.  See the GPOS/GSUB checks of name references
      # for an example of how we'd check.
      if not tests.check('name/unused'):
        return
      names = font_data.get_name_records(font)
      for i in names:
        # names 255 and below are reserved for standard names
        # names 256-32767 are for use by font tables
        # names 23 and 24 are for use by CPAL, so it might be considered a mistake if
        # these are present and no CPAL table is present or it doesn't use them.  Not
        # checking this for now.
        if i >= 256:
          warn('name/unused', 'Name', 'Name table has record #%d: "%s"' %
               (i, names[i]), is_error=False)

    def _check_name(actual, expected, keyname, is_re):
        """Set expected to '-' to require any name, set it to None if a name
        entry should not be present."""

        test_key = "name/" + keyname.replace(' ', '_')
        if not tests.check(test_key):
            return

        xre = ' it to match' if is_re else ''
        if expected:
            if not actual:
                if expected == '-':
                    warn(test_key, keyname, "The %s is not set." % keyname)
                else:
                    warn(test_key, keyname,
                         "The %s is not set, but was expecting%s '%s'" % (
                             keyname, xre, expected))
            elif expected != '-':
                if is_re:
                    match = re.match(expected, actual)
                else:
                    match = expected == actual
                if not match:
                    warn(test_key, keyname,
                         "The %s is '%s' but was expecting%s '%s'" % (
                             keyname, actual, xre, expected))
        elif actual:
            warn(test_key, keyname,
                 "Expected no %s, but got '%s'" % (keyname, actual))


    def check_name_table():
        if not tests.check('name'):
          return

        _check_unused_names()

        family_to_name_info = noto_names.family_to_name_info_for_phase(
            noto_phase)
        name_data = noto_names.name_table_data(
            noto_font, family_to_name_info, noto_phase)
        if not name_data:
            warn("name/unable_to_check", "Unable to check",
                 "No name data available for this font.")
            return

        names = font_data.get_name_records(font)

        def _check_idx(idx, expected, keyname):
          actual = names.get(idx, None)
          is_re = expected and expected[0] == '^' and expected[-1] == '$'
          _check_name(actual, expected, keyname, is_re=is_re)

        _check_idx(0, name_data.copyright_re, 'copyright')
        _check_idx(1, name_data.original_family, "family")
        _check_idx(2, name_data.original_subfamily, "subfamily")
        _check_idx(3, name_data.unique_id, "unique id")
        _check_idx(4, name_data.full_name, "full name")
        _check_idx(5, name_data.version_re, "version")
        _check_idx(6, name_data.postscript_name, "postscript name")
        _check_idx(7, name_data.trademark, "trademark")
        _check_idx(8, name_data.manufacturer, "manufacturer")
        _check_idx(9, name_data.designer, "designer")
        _check_idx(10, name_data.description_re, "description")
        _check_idx(11, name_data.vendor_url, "vendor url")
        _check_idx(12, name_data.designer_url, "designer url")
        _check_idx(13, name_data.license_text, "license")
        _check_idx(14, name_data.license_url, "license_url")

        if noto_font.is_cjk or noto_phase > 2:
            # 15 reserved
            _check_idx(16, name_data.preferred_family, "preferred family")
            _check_idx(17, name_data.preferred_subfamily, "preferred subfamily")
            # 18-20 (compatible full, sample text, postscript cid) - we don't check these
            _check_idx(21, name_data.wws_family, "wws family")
            _check_idx(22, name_data.wws_subfamily, "wws subfamily")
            # 23-24 (light/dark palette) - we don't check these

        if not tests.check('name/version'):
            return

        match = re.match(name_data.version_re, names[5])
        if not match:
            return # already caught above

        major_version = match.group(1)
        minor_version = match.group(2)
        if ((0 <= int(major_version) <= 65535)
            and (0 <= int(minor_version) <= 65535)):
            accuracy = len(minor_version)
            font_revision = printable_font_revision(font, accuracy)
            if font_revision != major_version + "." + minor_version:
                warn("name/version/match_head", "Font Revision",
                     "fontRevision in 'head' table is %s, "
                     "while font version in 'name' table is %s.%s." % (
                         font_revision, major_version, minor_version))
        else:
            warn("name/version/out_of_range", "Version",
                 "Version string has numerical parts outside the range "
                 "[0, 65535]: '%s'." % version_string)


    def _get_required_chars(noto_font, noto_phase, test_key):
      script_to_chars = _get_cmap_data_for_phase(noto_phase)
      # do we need to map font names/families to scripts differently based
      # on the phase?
      try:
        return script_to_chars[noto_font.script]
      except KeyError:
        warn(test_key, "Chars",
             "no char data for script %s in %s" % (
                 noto_font.script, noto_font.filepath))
        return None


    def _check_needed_chars(cmap, char_filter):
        # TODO(roozbeh): check the glyph requirements for controls specified at
        # https://www.microsoft.com/typography/otspec/recom.htm

        needed_chars = _get_required_chars(
            noto_font, noto_phase, 'cmap/script_required')
        if needed_chars == None:
             return

        # TODO: also check character coverage against Unicode blocks for
        # characters of script Common or Inherited

        if char_filter:
            # old_needed_size = len(needed_chars)
            needed_chars = set(itertools.ifilter(char_filter[1].accept, needed_chars))
            # TODO(dougfelt): figure out how to make this info available without messing up output
            # print 'filter needed char size: %d -> %d' % (old_needed_size, len(needed_chars))

        missing_chars = needed_chars - set(cmap.keys())
        if missing_chars:
            warn("cmap/script_required", "Chars",
                 "The following %d characters are missing from the font: %s."
                 % (len(missing_chars), printable_unicode_range(missing_chars)),
                 check_test=False)


    def _check_unexpected_chars(cmap, char_filter):
        expected_chars = _get_required_chars(
            noto_font, noto_phase, 'cmap/unexpected')
        if expected_chars == None:
            return
        unexpected_chars = set(cmap) - expected_chars
        if char_filter and unexpected_chars:
            unexpected_chars = set(itertools.ifilter(char_filter[1].accept, unexpected_chars))
        if unexpected_chars:
            warn("cmap/script_unexpected", "Chars",
                 "The following %d chars were not expected in the font: %s"
                 % (len(unexpected_chars), printable_unicode_range(unexpected_chars)),
                 is_error=False, check_test=False)


    def check_cmap_table():
        cmap_table = font['cmap']
        cmaps = {}
        # Format 14 is variation sequences
        expected_tables = [
            (4, 3, 1), (12, 3, 10), (14, 0, 5), (4, 0, 3), (12, 0, 4)]
        if font_props.is_cjk:
            expected_tables.extend([
                # Adobe says historically some programs used these to identify
                # the script in the font.  The encodingID is the quickdraw script
                # manager code.  These are dummy tables.
                (6, 1, 1),  # Japanese
                (6, 1, 2),  # Traditional Chinese
                (6, 1, 3),  # Korean
                (6, 1, 25), # Simplified Chinese
                ])
        for table in cmap_table.tables:
            if (table.format,
                table.platformID,
                table.platEncID) not in expected_tables:
                warn("cmap/tables/unexpected", "cmap",
                     "'cmap' has a subtable of (format=%d, platform=%d, encoding=%d), "
                     "which it shouldn't have." % (
                         table.format, table.platformID, table.platEncID))
            elif table != (12, 0, 4):
                if table.format in cmaps:
                    # if we have both 4,3,1 and 4,0,3, they should be aliases
                    # similarly if we have both 12,3,10 and 12,0,4
                    if id(table.cmap) != id(cmaps[table.format]):
                        warn("cmap/tables/notaliased", "cmap",
                             "'cmap' has two format %d subtables that are not"
                             " aliases" % table.format)
                else:
                  cmaps[table.format] = table.cmap

        if 4 not in cmaps:
            warn("cmap/tables/missing", "cmap",
                 "'cmap' does not have a format 4 subtable, but it should.")

        if 12 in cmaps:
            cmap = cmaps[12]
            # if there is a format 12 table, it should have non-BMP characters
            if max(cmap.keys()) <= 0xFFFF:
              warn("cmap/tables/format_12_has_bmp", "cmap",
                   "'cmap' has a format 12 subtable but no "
                   "non-BMP characters.")

            # format 4 table should be a subset of the format 12 one
            if tests.check('cmap/tables/format_4_subset_of_12') and 4 in cmaps:
                for char in cmaps[4]:
                    if char not in cmap:
                        warn("cmap/tables/format_4_subset_of_12", "cmap",
                             "U+%04X is mapped in cmap's format 4 subtable but "
                             "not in the format 12 one." % char, check_test=False)
                    elif cmaps[4][char] != cmap[char]:
                        warn("cmap/tables/format_4_subset_of_12", "cmap",
                             "U+%04X is mapped to %s in cmap's format 4 "
                             "subtable but to %s in the format 12 one." % (
                                 char, cmaps[4][char], cmap[char]), check_test=False)
        else:
            cmap = cmaps[4]


        if tests.check('cmap/required'):
            required_in_all_fonts = [
                0x0000, # .null
                0x000D, # CR
                0x0020] # space
            for code in required_in_all_fonts:
                if code not in cmap:
                    warn("cmap/required", "cmap",
                         "U+%04X is not mapped in cmap, but it should be (see "
                         "https://www.microsoft.com/typography/otspec/recom.htm)."
                             % code,
                         check_test=False)

        if not font_props.is_cjk and tests.check('cmap/script_required'):
            _check_needed_chars(cmap, tests.get_filter('cmap/script_required'))

        if tests.check('cmap/private_use'):
            needed_chars = _get_required_chars(
                noto_font, noto_phase, 'cmap/private_use')
            pua_filter = tests.get_filter('cmap/private_use')
            if pua_filter:
                pua_filter = pua_filter[1].accept
            def is_unwanted_pua(char):
                if char in needed_chars:
                    return False
                if not unicode_data.is_private_use(char):
                    return False
                if not pua_filter:
                    return True
                return pua_filter(char)

            privates_in_cmap = {char for char in cmap if is_unwanted_pua(char)}
            if privates_in_cmap:
                warn("cmap/private_use", "Chars",
                     "There should be no (non-required) private use characters "
                     "defined in the font, but there are %d: %s." % (
                         len(privates_in_cmap),
                         printable_unicode_range(privates_in_cmap)),
                     check_test=False)

        if tests.check('cmap/non_characters'):
            non_characters = frozenset(
                range(0xFDD0, 0xFDEF+1)
                + [0xFFFE + plane_no * 0x10000 for plane_no in range(0, 17)]
                + [0xFFFF + plane_no * 0x10000 for plane_no in range(0, 17)])
            non_characters_in_cmap = non_characters & set(cmap.keys())
            if non_characters_in_cmap:
                warn("cmap/non_characters", "Chars",
                     "There should be no non-characters defined in the font, but "
                     "there are: %s."
                         % printable_unicode_range(non_characters_in_cmap),
                     check_test=False)

        if tests.check('cmap/disallowed_ascii') and not (
            font_props.script == "Zsye" or
            font_props.script == "Latn" or
            font_props.script == "LGC" or
            font_props.is_cjk):
            ascii_letters = noto_data.ascii_letters()
            contained_letters = ascii_letters & set(cmap.keys())
            if contained_letters:
                warn("cmap/disallowed_ascii", "Chars",
                    "There should not be ASCII letters in the font, but there are: %s."
                     % printable_unicode_range(contained_letters),
                     check_test=False)

        if tests.check('cmap/unexpected'):
            # filter if present should list chars we do not want to warn on.
            _check_unexpected_chars(cmap, tests.get_filter('cmap/unexpected'))

        return cmap

    def check_variants():
        if not tests.check('cmap/variants'):
            return

        cmap = font_data.get_cmap(font)
        variant_cps = unicode_data.variant_data_cps()
        cps_with_variants = set(cmap.keys()) & variant_cps
        if not cps_with_variants:
            return

        vs_cmap = font_data.get_variation_sequence_cmap(font)
        if not vs_cmap:
            num = len(cps_with_variants)
            info = lint_config.write_int_ranges(cps_with_variants, sep=', ')
            if len(info) > 50:
              info = "not shown"
            warn("cmap/variants", "Variants",
                 "Font contains %d characters with standard variants, but has "
                 "no variation selector cmap table (%s)." % (num, info))
            return

        for cp in sorted(cps_with_variants):
            for sel, varcp, _ in sorted(unicode_data.get_variant_data(cp)):
                if not sel in vs_cmap.uvsDict:
                    warn("cmap/variants", "Variants",
                         "Char %04x has standard variant selector %04x, but "
                         "this selector is not in the variant table." %
                         (cp, sel), check_test=False )
                    continue
                sel_info = None
                for t in vs_cmap.uvsDict[sel]:
                    if t[0] == cp:
                        sel_info = t
                        break
                if not sel_info:
                    warn("cmap/variants", "Variants",
                         "Char %04x has no variant for selector %04x." %
                         (cp, sel), check_test=False)
                    continue

                if varcp != -1:
                    if varcp not in cmap:
                        warn("cmap/variants", "Variants",
                             "Char %04x and selector %04x should map to the "
                             "same glyph as char %04x, but %04x is not in the "
                             "cmap." % (cp, sel, varcp, varcp),
                             check_test=False)
                        continue

                    expected_glyphid = cmap[varcp]
                    sel_glyphid = sel_info[1] if sel_info[1] else cmap[cp]
                    if expected_glyphid != sel_glyphid:
                        warn("cmap/variants", "Variants",
                             "Char %04x and selector %04x map to glyph %s, "
                             "which should be the same glyph as is mapped to "
                             "by %04x, but its glyph is %s." %
                             (cp, sel, sel_glyphid, varcp, expected_glyphid),
                             check_test=False)


    def check_head_tables(cmap):
        if not tests.check('head'):
            return

        def check_ul_unicode_range():
            if not tests.check('head/os2/unicoderange'):
                return

            bitmap = font_data.get_os2_unicoderange_bitmap(font)
            expected_info = opentype_data.collect_unicoderange_info(cmap)
            expected_bitmap = font_data.unicoderange_info_to_bitmap(expected_info)
            difference = bitmap ^ expected_bitmap
            if not difference:
                return

            for bucket_index in range(128):
                if difference & (1 << bucket_index):
                    bucket_info = opentype_data.unicoderange_bucket_index_to_info(bucket_index)
                    range_name = opentype_data.unicoderange_bucket_info_name(bucket_info)
                    chars_in_bucket = sum(t[0] for t in expected_info if t[1][2] == bucket_index)
                    size_of_bucket = opentype_data.unicoderange_bucket_info_size(bucket_info)
                    set_unset = "not be set" if bitmap & (1 << bucket_index) else "be set"
                    warn("head/os2/unicoderange", "Range bit",
                         "ulUnicodeRange bit %d (%s) should %s (cmap has "
                         "%d of %d codepoints in this range)" %
                         (bucket_index, range_name, set_unset, chars_in_bucket, size_of_bucket),
                         check_test=False)

            # print printable_unicode_range(set(cmap.keys()))
            # print "expected %s" % font_data.unicoderange_bitmap_to_string(expected_bitmap)
            # print "have %s" % font_data.unicoderange_bitmap_to_string(bitmap)

        hhea_table = font["hhea"]
        upem = font['head'].unitsPerEm
        if upem == 2048:
          ui_ascent = UI_ASCENT
          ui_descent = UI_DESCENT
        else:
          ui_ascent = int(math.ceil(UI_ASCENT * upem / 2048.0))
          ui_descent = int(math.floor(UI_DESCENT * upem / 2048.0))

        if tests.check('head/hhea'):
            if font_props.is_UI_metrics:
                if hhea_table.ascent > ui_ascent:
                    warn("head/hhea/ascent", "Bounds",
                         "Value of ascent in 'hhea' table is %d, but should be %d."
                             % (hhea_table.ascent, ui_ascent))
                if hhea_table.descent < ui_descent:
                    warn("head/hhea/descent", "Bounds",
                         "Value of descent in 'hhea' table is %d, but should be %d."
                             % (hhea_table.descent, ui_descent))

            if hhea_table.lineGap != 0:
                warn("head/hhea/linegap", "Line Gap",
                     "Value of lineGap in 'hhea' table is %d, but should be 0."
                         % hhea_table.lineGap)

        vhea_table = font.get("vhea")
        if tests.check('head/vhea') and vhea_table:
            if vhea_table.lineGap != 0:
                warn("head/vhea/linegap", "Line Gap",
                     "Value of lineGap in 'vhea' table is %d, but should be 0."
                     % vhea_table.lineGap)

        os2_table = font["OS/2"]

        if tests.check('head/os2'):
            if os2_table.fsType != 0:
                warn("head/os2/fstype", "OS/2",
                     "Value of fsType in the 'OS/2' table is 0x%04X, but should "
                     "be 0." % os2_table.fsType)
            if os2_table.sTypoAscender != hhea_table.ascent:
                warn("head/os2/ascender", "OS/2",
                     "Value of sTypoAscender in 'OS/2' table (%d) is different "
                     "from the value of Ascent in 'hhea' table (%d), "
                     "but they should be equal." %
                     (os2_table.sTypoAscender, hhea_table.ascent))
            if os2_table.sTypoDescender != hhea_table.descent:
                warn("head/os2/descender", "OS/2",
                     "Value of sTypoDescender in 'OS/2' table (%d) is different "
                     "from the value of Descent in 'hhea' table (%d), "
                     "but they should be equal." %
                     (os2_table.sTypoDescender, hhea_table.descent))
            if os2_table.sTypoLineGap != 0:
                warn("head/os2/linegap", "OS/2",
                     "Value of sTypoLineGap in 'OS/2' table is %d, but "
                     "should be 0." % os2_table.sTypoLineGap)

            if os2_table.usWinAscent != hhea_table.ascent:
                warn("head/os2/winascent", "OS/2",
                     "Value of usWinAscent in 'OS/2' table (%d) is "
                     "different from the value of Ascent in 'hhea' table (%d), "
                     "but they should be equal." %
                     (os2_table.usWinAscent, hhea_table.ascent))
            if os2_table.usWinDescent != -hhea_table.descent:
                warn("head/os2/windescent", "OS/2",
                     "Value of usWinDescent in 'OS/2' table (%d) is different "
                     "from the opposite of value of Descent in 'hhea' table (%d), "
                     "but they should be opposites." %
                     (os2_table.usWinDescent, hhea_table.descent))
            if font_props.is_google and os2_table.achVendID != 'GOOG':
                warn("head/os2/achvendid", "OS/2",
                     "Value of achVendID in the 'OS/2' table is %s, "
                     "but should be GOOG." %
                     os2_table.achVendID)

            expected_weight = noto_fonts.WEIGHTS.get(font_props.weight, None)
            if not expected_weight:
                raise ValueError('unexpected weight: %s' % font_props.weight)

            # hack for windows GDI
            # remove this for phase 3
            if noto_phase <= 2:
              expected_weight = max(expected_weight, 250)

            if os2_table.usWeightClass != expected_weight:
                warn("head/os2/weight_class", "OS/2",
                     "Value of usWeightClass in 'OS/2' table is %d, but should "
                     "be %d." % (os2_table.usWeightClass, expected_weight))

            OS2_SEL_ITALIC_MASK = 1
            OS2_SEL_BOLD_MASK = 1 << 5
            OS2_SEL_REGULAR_MASK = 1 << 6
            OS2_SEL_USE_TYPO_METRICS_MASK = 1 << 7
            OS2_SEL_WWS_MASK = 1 << 8
            if os2_table.fsSelection & OS2_SEL_REGULAR_MASK:
                if os2_table.fsSelection & OS2_SEL_ITALIC_MASK:
                    warn("head/os2/fsselection", "OS/2",
                         "fsSelection Regular bit is set, so the Italic bit should be clear.")
                if os2_table.fsSelection & OS2_SEL_BOLD_MASK:
                    warn("head/os2/fsselection", "OS/2",
                         "fsSelection Regular bit is set, so the Bold bit should be clear.")

            if os2_table.fsSelection & OS2_SEL_USE_TYPO_METRICS_MASK:
                warn("head/os2/fsselection", "OS/2",
                     "UseTypoMetrics bit in fsSelection is set, but should be clear.")

            check_ul_unicode_range()

            if os2_table.panose.bFamilyType != 2:
              warn("head/os2/panose/family", "OS/2",
                   "Panose family value is %s but expected 2" %
                   os2_table.panose.bSerifStyle)

            expect_serif = noto_font.style == 'Serif' or noto_font.family in [
                'Cousine', 'Tinos']
            expected_serif_range_str = '2-10' if expect_serif else '11-15'
            serif_val = os2_table.panose.bSerifStyle
            is_serif = 1 < serif_val < 11
            if serif_val == 1:
              warn("head/os2/panose/serif", "OS/2",
                   "Panose serif value is 1 (no_fit) but expected 0 or %s" %
                   expected_serif_range_str)
            elif serif_val != 0 and expect_serif != is_serif:
              warn("head/os2/panose/serif", "OS/2",
                   "Panose serif value is %s but expected %s" %
                   (serif_val, expected_serif_range_str))

            # TODO(dougfelt): check condensed, semicondensed proportions?
            expect_mono = noto_font.is_mono or noto_font.family == 'Cousine'
            expect_mono_range_str = '9' if expect_mono else '2-4'
            proportion_val = os2_table.panose.bProportion
            is_mono = proportion_val == 9
            if proportion_val <= 1:

              warn("head/os2/panose/proportion", "OS/2",
                   "Panose proportion value is %s (%s) but "
                   "expected %s" % (
                       proportion_val,
                       'no_fit' if proportion_val == 1 else 'any',
                       expect_mono_range_str))
            elif expect_mono != is_mono:
              warn("head/os2/panose/proportion", "OS/2",
                   "Panose proportion value is %s but expected %s" %
                   (proportion_val, expect_mono_range_str))


    def check_vertical_limits():
        if 'glyf' not in font:
            return

        if not tests.check('bounds'):
            return

        upem = font['head'].unitsPerEm
        if upem == 2048:
          max_ui_height = MAX_UI_HEIGHT
          min_ui_height = MIN_UI_HEIGHT
        else:
          max_ui_height = int(math.ceil(MAX_UI_HEIGHT * upem / 2048.0))
          min_ui_height = int(math.floor(MIN_UI_HEIGHT * upem / 2048.0))

        glyf_table = font['glyf']
        us_win_ascent = font['OS/2'].usWinAscent
        us_win_descent = font['OS/2'].usWinDescent
        typo_ascent = font['OS/2'].sTypoAscender
        typo_descent = font['OS/2'].sTypoDescender

        # Build win ansi glyph set.  These we compare against usWinAscent/Descent, the
        # rest we compare against sTypoAscender/Descender. Of course, these should be
        # the same, and it's still ok for glyphs to exceed the typo ascender/descender--
        # but it should be exceptional.
        tmp_gids = set()
        cmap = font_data.get_cmap(font)
        for cp in lint_config.parse_int_ranges(WIN_ANSI_CODEPOINTS, True):
          if cp in cmap:
            tmp_gids.add(font.getGlyphID(cmap[cp], requireReal=True))
        win_ansi_gids = frozenset(tmp_gids)

        font_ymin = None
        font_ymax = None
        glyph_set = font.getGlyphSet()
        for glyph_index in range(len(glyf_table.glyphOrder)):
            glyph_name = glyf_table.glyphOrder[glyph_index]
            glyph = glyf_table[glyph_name]
            # Compute the ink's yMin and yMax

            ttglyph = glyph_set[glyph_name]
            ymin, ymax = render.get_glyph_cleaned_extents(ttglyph, glyph_set)
            font_ymin = render.min_with_none(font_ymin, ymin)
            font_ymax = render.max_with_none(font_ymax, ymax)

            if not tests.check('bounds/glyph'):
                continue

            is_win_ansi = glyph_index in win_ansi_gids
            if is_win_ansi:
              ascent_limit = us_win_ascent
              ascent_name = 'usWinAscent'
              descent_limit = -us_win_descent
              descent_name = 'usWinDescent'
            else:
              ascent_limit = typo_ascent
              ascent_name = 'sTypoAscent'
              descent_limit = typo_descent
              descent_name = 'sTypoDescent'

            if font_props.is_UI_metrics:
                if (tests.checkvalue('bounds/glyph/ui_ymax', glyph_index) and
                    ymax is not None and ymax > max_ui_height):
                    warn("bounds/glyph/ui_ymax", "UI Bounds",
                         "Real yMax for glyph %d (%s) is %d, which is more than "
                         "max ui height %d." % (
                             glyph_index, glyph_name, ymax, max_ui_height),
                         check_test=False)
                if (tests.checkvalue('bounds/glyph/ui_ymin', glyph_index) and
                    ymin is not None and ymin < min_ui_height):
                    warn("bounds/glyph/ui_ymin", "UI Bounds",
                         "Real yMin for glyph %d (%s) is %d, which is less than "
                         "min ui height %d." % (
                             glyph_index, glyph_name, ymin, min_ui_height),
                         check_test=False)

            if (tests.checkvalue('bounds/glyph/ymax', glyph_index) and ymax is not None and
                ymax > ascent_limit):
                warn("bounds/glyph/ymax", "Bounds",
                     "Real yMax for glyph %d (%s) is %d, which is higher than "
                     "the font's %s (%d), resulting in clipping." %
                     (glyph_index, glyph_name, ymax, ascent_name, ascent_limit),
                     check_test=False)

            if (tests.checkvalue('bounds/glyph/ymin', glyph_index) and ymin is not None and
                ymin < descent_limit):
                warn("bounds/glyph/ymin", "Bounds",
                     "Real yMin for glyph %d (%s) is %d, which is lower than "
                     "the font's %s (%d), resulting in clipping." %
                     (glyph_index, glyph_name, ymin, descent_name, descent_limit),
                     check_test=False)

        if tests.check('bounds/font'):
            if font_props.is_UI_metrics:
                if font_ymax > max_ui_height:
                    warn("bounds/font/ui_ymax", "UI Bounds",
                         "Real yMax is %d, but it should be less "
                         "than or equal to %d." % (font_ymax, max_ui_height))
                if font_ymin < min_ui_height:
                    warn("bounds/font/ui_ymin", "UI Bounds",
                         "Real yMin is %d, but it should be greater than or equal "
                         "to %d." % (font_ymin, min_ui_height))
            else:
                hhea_table = font["hhea"]
                if font_ymax > hhea_table.ascent:
                    warn("bounds/font/ymax", "Bounds",
                         "Real yMax %d, but it should be less "
                         "than or equal to the value of Ascent in 'hhea' table, "
                         "which is %d." % (font_ymax, hhea_table.ascent))
                if font_ymin < hhea_table.descent:
                    warn("bounds/font/ymin", "Bounds",
                         "Real yMin is %d, but it should be greater "
                         "than or equal to the value of Descent in 'hhea' table, "
                         "which is %d." % (font_ymin, hhea_table.descent))

    def check_for_intersections_and_off_curve_extrema():
        if 'glyf' not in font:
            return

        if variable:
            # ignore these for variable font masters
            return

        if not tests.check('paths'):
            return

        glyf_table = font['glyf']
        for glyph_index in range(len(glyf_table.glyphOrder)):
            glyph_name = glyf_table.glyphOrder[glyph_index]
            glyph = glyf_table[glyph_name]
            check_extrema = tests.check('paths/extrema')
            check_intersection = tests.check('paths/intersection')
            if glyph.numberOfContours not in [0, -1]:  # not empty or composite
                all_contours = []
                start_point = 0
                for contour in range(glyph.numberOfContours):
                    end_point = glyph.endPtsOfContours[contour]
                    # TODO(roozbeh): See if this matters, and potentially
                    # re-enable.
                    #
                    # if glyph.flags[start_point] == 0:
                    #   warn("Off-curve start", "The glyph '%s' has an "
                    #        "off-curve starting point in "its contour #%d."
                    #        % (glyph_name, contour+1))
                    curves_in_contour = []
                    for point in range(start_point, end_point + 1):
                        if glyph.flags[point] == 1:  # on-curve
                            next_point = point
                            while True:
                                next_point = next_circular_point(
                                    next_point, start_point, end_point)
                                if glyph.flags[next_point] == 1:  # on-curve
                                    break

                            curve = curve_between(
                                glyph.coordinates,
                                point, next_point,
                                start_point, end_point)

                            curves_in_contour.append(curve)

                            if not check_extrema:
                              continue
                            out_of_box = curve_has_off_curve_extrema(curve)
                            if out_of_box > 0:
                                warn("paths/extrema", "Extrema",
                                     "The glyph '%s' is missing on-curve extreme points "
                                     "in the segment between point %d=%s and point %d=%s "
                                     "by %f units."
                                     % (glyph_name,
                                        point,
                                        glyph.coordinates[point],
                                        next_point,
                                        glyph.coordinates[next_point],
                                        out_of_box),
                                      extrema_details,
                                     check_test=False)
                    start_point = end_point + 1
                    all_contours.append(curves_in_contour)

                if check_intersection:
                    result = curves_intersect(all_contours)
                    if result:
                        warn("paths/intersection", "Intersection",
                             "The glyph '%s' has intersecting "
                             "outlines: %s" % (glyph_name, result),
                             check_test=False)

    def check_gdef_table(cmap):
        """Validate the GDEF table."""
        if not tests.check('gdef'):
            return

        mark_glyphs = [code for code in cmap
                       if unicode_data.category(code) == 'Mn']
        try:
            class_def = font["GDEF"].table.GlyphClassDef.classDefs
        except (KeyError, AttributeError):
            class_def = None

        if tests.check('gdef/classdef'):
            names_of_classes = [
                "default class",
                "base glyph",
                "ligature glyph",
                "mark glyph",
                "component glyph"]
            if mark_glyphs and not class_def:
                warn("gdef/classdef/not_present", "Glyph Class",
                     "There is no GlyphClassDef subtable of GDEF table in the "
                     "font, while there are non-spacing combining characters: %s."
                     % printable_unicode_range(mark_glyphs),
                     is_error=False)
            elif mark_glyphs and not is_indic:
                for code in mark_glyphs:
                    glyph = cmap[code]
                    if glyph not in class_def:
                        if tests.checkvalue('gdef/classdef/unlisted', code):
                            warn("gdef/classdef/unlisted", "Glyph Class",
                                 "Glyph %s (U+%04X %s) is a combining mark, but is not "
                                 "assigned a value in the GDEF/GlyphClassDef table."
                                 % (glyph, code, unicode_data.name(code)),
                                 is_error=False, check_test=False)
                    elif (tests.checkvalue('gdef/classdef/combining_mismatch', code) and
                          class_def[glyph] != 3):
                        warn("gdef/classdef/combining_mismatch", "Glyph Class",
                             "Glyph %s (U+%04X %s) is a combining mark, but is "
                             "defined as class %d (%s) in the GDEF/GlyphClassDef "
                             "table." % (
                                 glyph,
                                 code,
                                 unicode_data.name(code),
                                 class_def[glyph],
                                 names_of_classes[class_def[glyph]]),
                             is_error=False, check_test=False)

            if class_def and not is_indic:
                for code in cmap:
                    glyph = cmap[code]
                    if glyph in class_def:
                        klass = class_def[glyph]
                        if (tests.checkvalue('gdef/classdef/not_combining_mismatch', code) and
                            klass == 3
                            and unicode_data.category(code) != "Mn"
                            and code not in noto_data.ACCEPTABLE_AS_COMBINING):
                            warn("gdef/classdef/not_combining_mismatch", "Glyph Class",
                                 "Glyph %s (U+%04X %s) is defined as class 3 "
                                 "(non-spacing) in the GDEF/GlyphClassDef table, "
                                 "but is of general category %s." % (
                                     cmap[code],
                                     code,
                                     unicode_data.name(code),
                                     unicode_data.category(code)),
                                 is_error=False, check_test=False)

        if tests.check('gdef/attachlist'):
            # check for duplicate attachment points in AttachList table
            # See https://code.google.com/p/noto/issues/detail?id=128#c20

            try:
                attach_point_list = font["GDEF"].table.AttachList.AttachPoint
            except (KeyError, AttributeError):
                attach_point_list = []

            for index, attach_point in enumerate(attach_point_list):
                points = attach_point.PointIndex
                if len(set(points)) != len(points):
                    warn("gdef/attachlist/duplicates", "Attach List",
                         "Entry #%d in GDEF.AttachList has duplicate points,"
                         "resulting in being rejected as a web font." % index)
                elif sorted(points) != points:
                    warn("gdef/attachlists/out_of_order", "Attach List",
                         "Points in entry #%d in GDEF.AttachList are not in "
                         "increasing order." % index)

        if tests.check('gdef/ligcaretlist'):
            # check that every ligature has a ligature caret in GDEF
            ligatures = []
            if class_def:
                for glyph in class_def:
                    if class_def[glyph] == 2:
                        ligatures.append(glyph)
            if ligatures:
                try:
                    lig_caret_list_coverage = (
                        font["GDEF"].table.LigCaretList.Coverage)
                except (KeyError, AttributeError):
                    lig_caret_list_coverage = None

                if not lig_caret_list_coverage:
                    if not is_indic:
                        warn("gdef/ligcaretlist/not_present", "Ligature Class",
                             "There is no LigCaretList data in the GDEF table, but "
                             "there are ligatures defined in GDEF: %s."
                             % ", ".join(ligatures))
                else:
                    if set(lig_caret_list_coverage.glyphs) - set(ligatures):
                        warn("gdef/ligcaretlist/not_ligature", "Ligature Class",
                             "Some glyphs are defined to have ligature carets in "
                             "GDEF table, but are not defined as ligatures in the "
                             "table: %s." % ", ".join(sorted(
                                 set(lig_caret_list_coverage.glyphs) -
                                 set(ligatures))))
                    elif set(ligatures) - set(lig_caret_list_coverage.glyphs):
                        if not is_indic:
                            warn("gdef/ligcaretlist/unlisted", "Ligature Class",
                                 "Some glyphs are defined as ligatures in "
                                 "the GDEF table, but don't have ligature carets: %s."
                                 % ", ".join(sorted(
                                     set(ligatures) -
                                     set(lig_caret_list_coverage.glyphs))))

    def check_complex_stylistic_set_name_ids(gsub_or_gpos):
        GSUB_OR_GPOS = gsub_or_gpos.upper()
        table = font[GSUB_OR_GPOS].table
        if not table.FeatureList:
          return

        name_id_set = None
        for index in range(table.FeatureList.FeatureCount):
          record = table.FeatureList.FeatureRecord[index]
          params = record.Feature.FeatureParams
          if isinstance(params, otTables.FeatureParamsStylisticSet):
            if not name_id_set:
              name_id_set = {r.nameID for r in font['name'].names}
            if not params.UINameID in name_id_set:
              warn("complex/%s/ui_name_id" % gsub_or_gpos, GSUB_OR_GPOS,
                   "Feature index %s (%s) has UINameID %d but it is not in the name table" % (
                       index, record.FeatureTag, params.UINameID))


    def check_shaping(font_file, strs, context, errors):
        text = '\n'.join(strs)
        temp_file = tempfile.NamedTemporaryFile(suffix='.txt')
        try:
            temp_file.write(text.encode("utf-8"))
            temp_file.flush()
            command = ['hb-shape', '--font-file=%s' % font_file,
                       '--text-file=%s' % temp_file.name]
            features = []
            if context != 'isol':
                features.append('-isol')
            if context:
                features.append(context)
            command.append('--features=%s' % ','.join(features))
            # print "command: %s" % ' '.join(command)
            result = subprocess.check_output(command)
            for src, res in zip(strs, result.splitlines()):
                if res.find('|') != -1:
                    errors.append((src, context, res))
        finally:
            temp_file.close()


    def check_gsub_variants():
        """Checks if harfbuzz can use GSUB to generate standard variants"""
        if not tests.check("complex/gsub/variants"):
            return

        cmap = font_data.get_cmap(font)
        variant_cps = unicode_data.variant_data_cps()
        cps_with_variants = set(cmap.keys()) & variant_cps
        any_strs = []
        isolate_strs = []
        initial_strs = []
        medial_strs = []
        final_strs = []
        for cp in sorted(cps_with_variants):
            data = unicode_data.get_variant_data(cp)
            for sel, _, ctx in sorted(data):
                line = unichr(cp) + unichr(sel);
                if ctx == 0:
                  any_strs.append(line)
                  continue
                if ctx & 1:
                  isolate_strs.append(line)
                if ctx & 2:
                  initial_strs.append(line)
                if ctx & 4:
                  medial_strs.append(line)
                if ctx & 8:
                  final_strs.append(line)

        errors = []
        font_file = font_props.filepath
        check_shaping(font_file, any_strs, '', errors)
        check_shaping(font_file, isolate_strs, 'isol', errors)
        check_shaping(font_file, initial_strs, 'init', errors)
        check_shaping(font_file, medial_strs, 'medi', errors)
        check_shaping(font_file, final_strs, 'fina', errors)
        if errors:
            erroritems = []
            for src, context, res in errors:
                srctext = ' '.join("%04x" % ord(cp) for cp in src)
                ctx = (" (%s)" % context) if context else ''
                erroritems.append("%s%s: %s" % (srctext, ctx, res))
            errorinfo = ', '.join(erroritems)
            warn("complex/gsub/variants", "GSUB",
                 "Expected GSUB to generate all standard variants, but %d "
                 "cases did not (%s)" % (len(errors), errorinfo))

    def check_gpos_and_gsub_tables():
        if not tests.check('complex'):
            return

        whitelist = [
            'Hluw',  # Anatolian Hieroglyphs
            'Cari',  # Carian
            'Xsux',  # Cuneiform
            'Cprt',  # Cypriot
            'Dsrt',  # Deseret
            'Egyp',  # Egyptian Hieroglyphs
            'Armi',  # Imperial Aramaic
            'Linb',  # Linear B
            'Lisu',  # Lisu
            'Lyci',  # Lycian
            'Lydi',  # Lydian
            'Ogam',  # Ogham
            'Olck',  # Ol Chiki
            'Ital',  # Old Italic
            'Xpeo',  # Old Persian
            'Sarb',  # Old South Arabian
            'Orkh',  # Old Turkic
            'Osma',  # Osmanya
            'Phnx',  # Phoenician
            'Runr',  # Runic
            'Shaw',  # Shavian
            'Ugar',  # Ugaritic
            'Vaii',  # Vai
            'Yiii',  # Yi
        ]
        if font_props.script in whitelist:
            return

        if "GPOS" not in font:
            warn("complex/gpos/missing", "GPOS",
                 "There is no GPOS table in the font.")
        else:
            check_complex_stylistic_set_name_ids('gpos')

        # Assume no GSUB necessary for Adlm
        if font_props.script == 'Adlm':
            return

        if "GSUB" not in font:
            warn("complex/gsub/missing", "GSUB",
                 "There is no GSUB table in the font.")
        else:
            check_complex_stylistic_set_name_ids('gsub')
            check_gsub_variants()

        #TODO: Add more script-specific checks

    def check_for_bidi_pairs(cmap):
        """Checks for proper support of bidi mirroring in the font.

        For each bidi mirroring character in the font, we wake sure that: if it
        is in OMPL, its mirror pair should also be in the cmap, and the first
        character should not mapped by 'rtlm'. If the character is not in OMPL,
        it should be mapped by 'rtlm'.

        Only the first 'rtlm' feature in the font is used.
        """
        if not tests.check('bidi'):
            return

        # need to discuss this with Adobe

        rtlm = {}
        if "GSUB" in font:
            try:
              feature_record = font["GSUB"].table.FeatureList.FeatureRecord
            except AttributeError:
              warn("bidi", "bidi",
                   "GSUB table with no feature record", is_error=False)
              feature_record = []
            for record in feature_record:
                if record.FeatureTag == "rtlm":  # FIXME
                    for lookup_number in record.Feature.LookupListIndex:
                        lookup = font["GSUB"].table.LookupList.Lookup[
                            lookup_number]
                        lookup_type = lookup.LookupType
                        if lookup_type == 7:  # GSUB extension
                            assert lookup.SubTableCount == 1
                            lookup_type = lookup.SubTable[0].ExtensionLookupType
                            subtables = [lookup.SubTable[0].ExtSubTable]
                        else:
                            subtables = lookup.SubTable

                        assert lookup_type == 1, (
                            "Don't know how to handle 'rtlm' features with "
                            "lookup type other than 1.")
                        for subtable in subtables:
                            for key in subtable.mapping.keys():
                                rtlm[key] = subtable.mapping[key]
                    break

        ompl = opentype_data.OMPL
        for code in sorted(cmap):
            if (unicode_data.is_private_use(code)
                    or not unicode_data.mirrored(code)):
                if cmap[code] in rtlm:
                    warn("bidi/rtlm_non_mirrored", "Bidi",
                         "The 'rtlm' feature in the font applies to the glyph "
                         "for U+%04X (%s), but it shouldn't, since the "
                         "character is not bidi mirroring." % (
                             code, cmap[code]))
                continue  # skip the rest of the tests

            # The following tests are only applied to bidi mirroring characters
            if code in ompl:
                if cmap[code] in rtlm:
                    warn("bidi/ompl_rtlm", "Bidi",
                         "The 'rtlm' feature in the font applies to the glyph "
                         "for U+%04X (%s), but it shouldn't, since the "
                         "character is in the OMPL list." % (code, cmap[code]))

                mirrored_pair = ompl[code]
                if mirrored_pair not in cmap:
                    warn("bidi/ompl_missing_pair", "Bidi",
                         "The character U+%04X (%s) is supported in the font, "
                         "but its bidi mirrored pair U+%04X (%s) is not." % (
                             code, unicode_data.name(code),
                             mirrored_pair, unicode_data.name(mirrored_pair)))
            else:
                if cmap[code] not in rtlm:
                    warn("bidi/rtlm_unlisted", "Bidi",
                         "No 'rtlm' feature is applied to the glyph "
                         "for U+%04X (%s), but one should be applied, since "
                         "the character is a bidi mirroring character that is "
                         "not in the OMPL list." % (
                             code, cmap[code]))

    def check_hints():
        if not 'glyf' in font:
            return

        if not tests.check('hints'):
            return

        expected_to_be_hinted = font_props.is_hinted
        expected_to_be_unhinted = not expected_to_be_hinted

        # There should be no fpgm, prep, or cvt tables in unhinted fonts
        if expected_to_be_unhinted:
            for table_name in ['fpgm', 'prep', 'cvt']:
                if table_name in font:
                    warn("hints/unexpected_tables", "Hints",
                         "The font is supposed to be unhinted, but it has "
                         "a '%s' table." % table_name)

        glyf_table = font['glyf']
        check_unexpected_bytecode = tests.check('hints/unexpected_bytecode')
        for glyph_index in range(len(glyf_table.glyphOrder)):
            glyph_name = glyf_table.glyphOrder[glyph_index]
            glyph = glyf_table[glyph_name]
            if glyph.numberOfContours > 0:
                bytecode = glyph.program.bytecode
                if expected_to_be_unhinted:
                    if check_unexpected_bytecode and bytecode:
                        warn("hints/unexpected_bytecode", "Hints",
                             "The font is supposed to be unhinted, but "
                             "glyph '%s' has hints." % glyph_name,
                             check_test=False)
                else:
                    if not bytecode and tests.checkvalue('hints/missing_bytecode', glyph_index):
                        warn("hints/missing_bytecode", "Hints",
                             "The font is supposed to be hinted, but "
                             "glyph '%s' (%d) doesn't have hints." % (glyph_name, glyph_index),
                             check_test=False)

    def check_explicit_advances():
        """Check some cases where we expect advances to be explicitly related."""
        if not tests.check('advances'):
            return

        cmap = font_data.get_cmap(font)

        def get_horizontal_advance(codepoint):
            return font_data.get_glyph_horizontal_advance(font, cmap[codepoint])

        def expect_width(codepoint, expected, low_divisor=None, high_divisor=None,
                         label='advances/whitespace', is_error=True):
            # it is ok if the font does not support the tested codepoint
            if codepoint not in cmap:
                return
            # no low divisor means exact match of the expected advance
            if not low_divisor:
                low_divisor = 1
                slop = 0
            else:
                slop = 1
            adv = get_horizontal_advance(codepoint)
            if not high_divisor:
                exp = int(round(float(expected) / low_divisor))
                if abs(adv - exp) > slop:
                    glyph_name = cmap[codepoint]
                    glyph_id = font.getGlyphID(glyph_name)
                    warn(label, "Advances",
                         "The advance of U+%04x (%s, glyph %d) is %d, but expected %d." %
                         (codepoint, glyph_name, glyph_id, adv, exp),
                         check_test=False, is_error=is_error)
            else:
                # note name switch, since the higher divisor returns the lower value
                high_exp = int(round(float(expected) / low_divisor))
                low_exp =  int(round(float(expected) / high_divisor))
                if not (low_exp - slop <= adv <= high_exp + slop):
                    glyph_name = cmap[codepoint]
                    glyph_id = font.getGlyphID(glyph_name)
                    warn(label, "Advances",
                         "The advance of U+%04x (%s, glyph %d) is %d, but expected between "
                         "%d and %d." % (codepoint, glyph_name, glyph_id, adv, low_exp,
                                         high_exp),
                         check_test=False, is_error=is_error)

        digit_char = ord('0')
        period_char = ord('.')
        comma_char = ord(',')
        space_char = ord(' ')
        tab_char = ord('\t')
        nbsp_char = 0x00a0

        if digit_char in cmap:
            digit_width = get_horizontal_advance(digit_char)
            if tests.check('advances/digits'):
                for i in range(10):
                    digit = ord('0') + i
                    width = get_horizontal_advance(digit)
                    if width != digit_width:
                        warn("advances/digits", "Advances",
                             "The advance of '%s' (%d) is different from that of '0' (%d)." %
                             (chr(digit), width, digit_width),
                             check_test=False)

        if period_char in cmap:
            period_width = get_horizontal_advance(period_char)
            if tests.check('advances/comma_period') and comma_char in cmap:
                expect_width(comma_char, period_width, label='advances/comma_period',
                             is_error=False)

        if tests.check('advances/whitespace'):
            if font_props.is_mono:
                space_width = get_horizontal_advance(space_char)
                cps = [ tab_char, nbsp_char ] + range(0x2000, 0x200B)
                for cp in cps:
                    if cp in cmap:
                        expect_width(cp, space_width)
            else:
                if tab_char in cmap or nbsp_char in cmap:
                    space_width = get_horizontal_advance(space_char);
                    if tab_char in cmap:
                        # see https://www.microsoft.com/typography/otspec/recom.htm
                        expect_width(tab_char, space_width)
                    if nbsp_char in cmap:
                        expect_width(nbsp_char, space_width)

                em_width = font['head'].unitsPerEm
                expect_width(0x2000, em_width, 2) # en_quad
                expect_width(0x2001, em_width)    # em_quad
                expect_width(0x2002, em_width, 2) # en_space
                expect_width(0x2003, em_width)    # em_space
                expect_width(0x2004, em_width, 3) # three-per-em space
                expect_width(0x2005, em_width, 4) # four-per-em space
                expect_width(0x2006, em_width, 6) # six-per-em space
                if digit_char in cmap:
                    expect_width(0x2007, digit_width) # figure space
                if period_char in cmap:
                    expect_width(0x2008, period_width) # punctuation space
                # see http://unicode.org/charts/PDF/U2000.pdf, but microsoft (below)
                # says French uses 1/8 em.
                expect_width(0x2009, em_width, 5, 6) # thin space
                # see http://www.microsoft.com/typography/developers/fdsspec/spaces.htm
                expect_width(0x200A, em_width, 10, 16) # hair space
                expect_width(0x200B, 0) # zero width space

        if tests.check('advances/spacing_marks'):
          spacing_marks = lint_config.parse_int_ranges(
              "02C8 02CA-02D7 02DE 02DF 02EC 02ED 02EF-02F2 02F4-02FF", True)
          for cp in spacing_marks:
            if cp not in cmap:
              continue
            if not get_horizontal_advance(cp):
              warn("advances/spacing_marks", "Advances",
                   "The spacing mark %s (%04x) should have a non-zero advance." % (
                       unichr(cp), cp));

    def check_stems(cmap):
        if not 'glyf' in font:
            return

        if not tests.check('stem'):
            return

        # Only implemented for Ogham, currently
        # FIXME: Add support for Arabic, Syriac, Mongolian, Phags-Pa,
        # Devanagari, Bengali, etc
        joins_to_right = set(range(0x1680, 0x169B+1))
        joins_to_left = set(range(0x1680, 0x169A+1) + [0x169C])
        all_joining = joins_to_right | joins_to_left

        glyf_table = font['glyf']
        metrics_dict = font['hmtx'].metrics
        check_left_joining = tests.check('stem/left_joining')
        check_right_joining = tests.check('stem/right_joining')
        for code in all_joining & set(cmap):
            glyph_name = cmap[code]
            advance_width, lsb = metrics_dict[glyph_name]
            if check_left_joining and code in joins_to_left:
                if lsb != 0:
                    warn("stem/left_joining", "Stem",
                         "The glyph for U+%04X (%s) is supposed to have a stem "
                         "connecting to the left, but its left side bearing "
                         "is %d instead of 0."
                         % (code, unicode_data.name(code), lsb),
                         check_test=False)
            if check_right_joining and code in joins_to_right:
                glyph = glyf_table[glyph_name]
                rsb = advance_width - (lsb + glyph.xMax - glyph.xMin)
                if rsb != -70:
                    warn("stem/right_joining", "Stem",
                         "The glyph for U+%04X (%s) is supposed to have a stem "
                         "connecting to the right, but it's right side bearing "
                         "is %d instead of -70."
                         % (code, unicode_data.name(code), rsb),
                         check_test=False)

    def check_accessiblity(cmap):
        """Test if all glyphs are accessible through cmap, decomps, or GSUB.

        This is done using the font subsetter. We ask the subsetter to subset
        for all Unicode characters in the cmap table, and see if every glyph is
        covered after subsetting.
        """
        if not tests.check('reachable'):
            return

        test_filter = tests.get_filter('reachable')
        glyph_name_to_id = font.getReverseGlyphMap().copy()

        all_glyphs = set(font.getGlyphOrder())
        subsetter = subset.Subsetter()
        subsetter.populate(unicodes=cmap.keys())
        try:
          subsetter._closure_glyphs(font)
        except Exception as e:
          warn("reachable", "Reachability",
               "Subsetter failure, bad/missing tables?: '%s'" % e)
          return

        unreachable_glyphs = all_glyphs - subsetter.glyphs_all
        if unreachable_glyphs:
            reported_glyphs = set()
            reported_list = []
            for glyph_name in unreachable_glyphs:
                glyph_id = glyph_name_to_id[glyph_name]
                if not test_filter or test_filter[1].accept(glyph_id):
                    if glyph_name not in reported_glyphs:
                        reported_glyphs.add(glyph_name)
                        reported_list.append((glyph_name, glyph_id))
            if reported_list:
                report_info = ', '.join('%s (%d)' % t for t in sorted(reported_list))
                warn("reachable", "Reachability",
                     "The following %d glyphs are unreachable in the font: %s." %
                     (len(reported_glyphs), report_info),
                     check_test=False)


    ### actual start of check_font fn


    # python 2.7 does not have nonlocal, so hack around it
    suppressed_err_count = [0]
    err_count = [0]
    suppressed_warn_count = [0]
    warn_count = [0]

    font_path = path.expanduser(font_props.filepath)
    font = ttLib.TTFont(font_path)

    is_indic = font_props.script in {
        "Deva", "Beng", "Guru", "Gujr", "Orya",
        "Taml", "Telu", "Knda", "Mlym", "Sinh",
        "Khmr" }

    fi = lint_config.FontInfo(
        filename=path.basename(font_path),
        name=font_props.family,
        style=font_props.style,
        script=font_props.script,
        variant=font_props.variant,
        weight=font_props.weight,
        monospace=font_props.is_mono,
        hinted=font_props.is_hinted,
        vendor=font_props.vendor,
        version=printable_font_revision(font, accuracy=3 if font_props.vendor == 'Adobe' else 2))
    tests = lint_spec.get_tests(fi)

    if filename_error:
        if filename_error == 'script':
            warn("filename/script", "File name",
                 "Style %s also needs a script mentioned in the "
                 "file name." % font_props.style)
        elif filename_error == 'name':
            warn("filename/name", "File name",
                 "File name '%s' does not match the Noto font naming guidelines."
                 % path.basename(font_props.filepath))


    check_name_table()
    cmap = check_cmap_table()
    check_variants()
    check_head_tables(cmap)
    check_vertical_limits()
    check_for_intersections_and_off_curve_extrema()
    check_gdef_table(cmap)
    check_gpos_and_gsub_tables()
    check_for_bidi_pairs(cmap)
    check_hints()
    check_explicit_advances()
    check_stems(cmap)

    # This must be done at the very end, since the subsetter may change the font
    check_accessiblity(cmap)

    warn("info", "info",
         "supported characters: " + printable_unicode_range(cmap.keys()),
         check_test=False)

    if runlog:
        log = sorted(tests.runlog())
        count = len(log)
        if count:
          print 'Ran %d test%s:\n  %s' % (count, 's' if count != 1 else '',
                                        '\n  '.join(log))
        else:
          print 'Ran no tests.'
    if skiplog:
        log = sorted(tests.skiplog())
        count = len(log)
        if len(log):
          print 'Skipped %d test/group%s:\n  %s' % (count, 's' if count != 1 else '',
                                            '\n  '.join(log))
        else:
          print 'Skipped no tests'

    # TODO(roozbeh):
    # * Check that hintedness based on data in the glyf table
    #   matches metadata (file location, header data)
    # * Check GSUB coverage, based on script
    # * Check gasp values
    # * Add support for TTC fonts
    # * Check ulCodePageRange values


def get_lint_spec(spec_file, extra_specs):
  """Return a LintSpec from spec_file supplemented with extra_specs.
  If spec_file is None, only use extra_specs."""

  spec = None
  if spec_file != 'None':
    spec = lint_config.parse_spec_file(spec_file)
  return lint_config.parse_spec(extra_specs, spec)


def parse_font_props(font_props_file):
  """Return a list of FontProps objects."""
  with open(font_props_file) as f:
    font_spec = f.read()
  spec_data = json.loads(font_spec)
  return [FontProps(**m) for m in spec_data]


def write_font_props(font_props):
  print json.dumps(font_props._asdict())


def main():
    default_config_file = notoconfig.get(
        'lint_config', '[tools]/nototools/data/lint_config.txt')

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        help="produces csv output to import into a spreadsheet",
        action="store_true")
    parser.add_argument(
        "--info",
        help="includes informational messages in the output",
        action="store_true")
    parser.add_argument(
        "--suppress_extrema_details",
        dest="extrema_details",
        default=True,
        action="store_false",
        help="only summarize extrema issues")
    parser.add_argument(
        "--csv_header",
        help="write header line when generating csv output",
        action="store_true")
    parser.add_argument(
        "font_files",
        metavar="font",
        nargs="*",
        help="a font file to check, can omit if font_spec is provided")
    parser.add_argument(
        "--font_props_file",
        metavar="file",
        help="file containing json describing font file paths and expected properties")
    parser.add_argument(
        "--config_file",
        help="location of config file (default %s, 'None' for none)" % default_config_file,
        metavar='file',
        default=default_config_file)
    parser.add_argument(
        "--config",
        help="extra config spec to process after config file",
        metavar='lint_spec')
    parser.add_argument(
        "--runlog",
        help="show tags of run tests",
        action="store_true")
    parser.add_argument(
        "--skiplog",
        help="show tags of skipped tests",
        action="store_true")
    parser.add_argument(
        "--dump_font_props",
        help="write font props for files",
        action="store_true")
    parser.add_argument(
        "-nw", "--nowarn",
        help="suppress warning messages",
        action="store_true")
    parser.add_argument(
        "-q", "--quiet",
        help="don't print file names unless there are errors or warnings",
        action="store_true")
    parser.add_argument(
        "-p", "--phase",
        help="set noto phase for lint compatibility (default 3)",
        metavar='phase', type=int, default=3)
    parser.add_argument(
        "-v", "--variable",
        help="do checks appropriate to masters for variable fonts.",
        action="store_true")

    arguments = parser.parse_args()

    if arguments.dump_font_props:
        for font_file_path in arguments.font_files:
            font_file_path = tool_utils.resolve_path(font_file_path)
            font_props, filename_error = get_font_properties_with_fallback(
                font_file_path, phase=arguments.phase)
            if filename_error:
                print '#Error for %s: %s' % (font_file_path, filename_error)
            else:
                write_font_props(font_props)
        return

    config_file = tool_utils.resolve_path(arguments.config_file)
    lint_spec = get_lint_spec(config_file, arguments.config)

    if arguments.csv and arguments.csv_header:
        print("Type,Script,Style,Variant,Subfamily,Manufacturer,Category,"
              "Hint Status,File Name,Revision,Issue")

    for font_file_path in arguments.font_files:
        font_file_path = tool_utils.resolve_path(font_file_path)
        font_props, filename_error = get_font_properties_with_fallback(
            font_file_path, phase=arguments.phase)
        if not font_props:
            print '## ERROR: cannot parse %s' % font_file_path
        else:
            check_font(font_props,
                       filename_error,
                       lint_spec,
                       arguments.runlog,
                       arguments.skiplog,
                       arguments.csv,
                       arguments.info,
                       arguments.extrema_details,
                       arguments.nowarn,
                       arguments.quiet,
                       arguments.phase,
                       arguments.variable)
    if arguments.font_props_file:
        font_props_list = parse_font_props(arguments.font_props_file)
        for font_props in font_props_list:
             check_font(font_props,
                        '',
                        lint_spec,
                        arguments.runlog,
                        arguments.skiplog,
                        arguments.csv,
                        arguments.info,
                        arguments.extrema_details,
                        arguments.nowarn,
                        arguments.quiet,
                        arguments.phase,
                        arguments.variable)

    if not arguments.csv:
        print "------"
        if _processed_files == 1:
            print "Finished linting 1 file."
        else:
            print "Finished linting %d files." % _processed_files
        if _processed_files > 1:
            if _processed_files_with_errors:
                print "%d file%s had errors." % (
                    _processed_files_with_errors,
                    '' if _processed_files_with_errors == 1 else 's')
            if _processed_files_with_warnings:
                print "%d file%s had warnings." % (
                    _processed_files_with_warnings,
                    '' if _processed_files_with_warnings == 1 else 's')

if __name__ == "__main__":
    main()
