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

"""Rendering-related test routines."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import json
import os
import subprocess

import font_caching

from fontTools.pens.boundsPen import BoundsPen

def min_with_none(first, second):
    """Returns the minimum of the two inputs, ignoring Nones."""
    if first is None:
        return second
    elif second is None:
        return first
    else:
        return min(first, second)


def max_with_none(first, second):
    """Returns the maximum of the two inputs, ignoring Nones."""
    if first is None:
        return second
    elif second is None:
        return first
    else:
        return max(first, second)


def transform_y(transform, y_value):
    """Applies a transform matrix to a y coordinate."""
    return int(round(y_value * transform[1][1]))


def get_glyph_cleaned_extents(ttglyph, glyf_set):
    pen = BoundsPen(glyf_set, ignoreSinglePoints=True)
    ttglyph.draw(pen)
    if not pen.bounds:
      return None, None
    return pen.bounds[1], pen.bounds[3]


def get_glyph_cleaned_extents_OLD(glyph, glyf_table):
    """Get the vertical extent of glyphs, ignoring single-point contours.

    This is take care of weirdness in the various fonts, who may need the
    single-point contours for hinting or glyph positioning, or may have
    forgotten to clean them up."""

    try:
        return glyph.cleanedYMin, glyph.cleanedYMax
    except AttributeError:
        glyph.expand(glyf_table)

        if glyph.numberOfContours == 0:  # is empty
            glyph.cleanedYMin = None
            glyph.cleanedYMax = None
            return None, None
        elif glyph.numberOfContours == -1:  # has components
            max_height = None
            min_height = None
            for component in glyph.components:
                component_ymin, component_ymax = get_glyph_cleaned_extents(
                    glyf_table.glyphs[component.glyphName],
                    glyf_table)

                if hasattr(component, 'transform'):
                    transform = component.transform
                    assert transform[1][0] == transform[0][1] == 0, (
                        "Can't handle complex transforms")
                else:
                    transform = [[1, 0], [0, 1]]
                max_height = max_with_none(
                    max_height,
                    transform_y(transform, component_ymax) + component.y)
                min_height = min_with_none(
                    min_height,
                    transform_y(transform, component_ymin) + component.y)
        else:
            # Set points_to_ignore to the list of all single-point contours
            points_to_ignore = set()
            previous_end_point = -1
            for end_point in glyph.endPtsOfContours:
                if end_point == previous_end_point + 1:
                    points_to_ignore.add(end_point)

                previous_end_point = end_point

            max_height = None
            min_height = None
            for index, point in enumerate(glyph.coordinates):
                if index in points_to_ignore:
                    continue

                y_value = point[1]
                max_height = max_with_none(max_height, y_value)
                min_height = min_with_none(min_height, y_value)

        glyph.cleanedYMin = min_height
        glyph.cleanedYMax = max_height
        return min_height, max_height


def get_glyph_vertical_extents(glyph_id, font_file_name):
    """Returns visible vertical extents given a glyph ID and font name."""
    font = font_caching.open_font(font_file_name)
    glyf_set = font.getGlyphSet()

    glyph_name = font.getGlyphName(glyph_id)
    ttglyph = glyf_set[glyph_name]

    return get_glyph_cleaned_extents(ttglyph, glyf_set)


# FIXME: figure out how to make this configurable
HARFBUZZ_DIR = os.getenv('HOME') + os.sep + 'harfbuzz'
HB_SHAPE_PATH = HARFBUZZ_DIR + os.sep + 'util' + os.sep + 'hb-shape'


def run_harfbuzz_on_text(text, font_file_name, language, extra_parameters=None):
    """Runs HarfBuzz on input text and return JSON shaping information."""
    hb_parameters = [
        HB_SHAPE_PATH,
        '--output-format=json',
        '--no-glyph-names',  # Some fonts have empty glyph names
        '--font-file=%s' % font_file_name]

    if language:
        hb_parameters.append('--language=%s' % language)

    if extra_parameters is not None:
        hb_parameters += extra_parameters

    hb_process = subprocess.Popen(
        hb_parameters,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE)

    return hb_process.communicate(input=text.encode('UTF-8'))[0]


def get_line_extents_from_json(json_data, font_file_name):
    """Find the vertical extents of a line based on HarfBuzz JSON output."""
    max_height = None
    min_height = None
    for glyph_position in json.loads(json_data):
        glyph_id = glyph_position['g']
        glyph_ymin, glyph_ymax = get_glyph_vertical_extents(
            glyph_id, font_file_name)

        if glyph_ymax is not None:
            glyph_vertical_offset = glyph_position['dy']
            max_height = max_with_none(
                max_height, glyph_ymax + glyph_vertical_offset)
            min_height = min_with_none(
                min_height, glyph_ymin + glyph_vertical_offset)

    return min_height, max_height


def test_text_vertical_extents(
    text, font_file_name, min_allowed, max_allowed, language=None):
    """Runs given text through HarfBuzz to find cases that go out of bounds."""

    hb_output = run_harfbuzz_on_text(text, font_file_name, language)

    split_text = text.split('\n')
    exceeding_lines = []
    for line_no, output_line in enumerate(hb_output.split('\n')):
        if not output_line:
            continue

        min_height, max_height = get_line_extents_from_json(
            output_line, font_file_name)

        if min_height is None:
            continue
        if min_height < min_allowed or max_height > max_allowed:
            exceeding_lines.append(((min_height, max_height),
                                    split_text[line_no]))

    return exceeding_lines
