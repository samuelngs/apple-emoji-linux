# Copyright 2016 Google Inc. All Rights Reserved.
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


"""Provides ShapeDiffFinder, which finds differences in OTF/TTF glyph shapes.

ShapeDiffFinder takes in two paths, to font binaries. It then provides methods
that compare these fonts, storing results in a report dictionary. These methods
are `find_area_diffs`, which compares glyph areas, `find_rendered_diffs`, which
compares harfbuzz output using PIL, and `find_shape_diffs`, which takes the
difference of shapes and calculates the area.

Some caveats: glyph areas can be the same even if the shapes are wildly
different (though they're useful for shapes that should be identical except
for some offset). Image comparison is usually either slow (hi-res) or inaccurate
(lo-res). Still, these are usually useful for raising red flags and catching
large errors.
"""

from __future__ import division

import os
from PIL import Image
import re
import StringIO
import subprocess
import tempfile

import booleanOperations
from defcon import Glyph
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from ufoLib.pointPen import PointToSegmentPen

from nototools.glyph_area_pen import GlyphAreaPen
from nototools import hb_input

GDEF_UNDEF = 0
GDEF_MARK = 3
GDEF_LABELS = ['no class', 'base', 'ligature', 'mark', 'component']


class ShapeDiffFinder:
    """Provides methods to report diffs in glyph shapes between OT Fonts."""

    def __init__(
            self, file_a, file_b, stats, ratio_diffs=False, diff_threshold=0):
        self.path_a = file_a
        self.font_a = TTFont(self.path_a)
        self.glyph_set_a = self.font_a.getGlyphSet()
        self.gdef_a = {}
        if 'GDEF' in self.font_a and not self.font_a['GDEF'].table.GlyphClassDef is None:
            self.gdef_a = self.font_a['GDEF'].table.GlyphClassDef.classDefs

        self.path_b = file_b
        self.font_b = TTFont(self.path_b)
        self.glyph_set_b = self.font_b.getGlyphSet()
        self.gdef_b = {}
        if 'GDEF' in self.font_b and not self.font_b['GDEF'].table.GlyphClassDef is None:
            self.gdef_b = self.font_b['GDEF'].table.GlyphClassDef.classDefs

        for stat_type in (
                'compared', 'untested', 'unmatched', 'unicode_mismatch',
                'gdef_mark_mismatch', 'zero_width_mismatch', 'input_mismatch'):
            if stat_type not in stats:
                stats[stat_type] = []
        self.stats = stats

        self.ratio_diffs = ratio_diffs
        self.diff_threshold = diff_threshold
        self.basepath = os.path.basename(file_a)

    def find_area_diffs(self):
        """Report differences in glyph areas."""

        self.build_names()

        pen_a = GlyphAreaPen(self.glyph_set_a)
        pen_b = GlyphAreaPen(self.glyph_set_b)

        mismatched = {}
        for name in self.names:
            self.glyph_set_a[name].draw(pen_a)
            area_a = pen_a.pop()
            self.glyph_set_b[name].draw(pen_b)
            area_b = pen_b.pop()
            if area_a != area_b:
                mismatched[name] = (area_a, area_b)

        stats = self.stats['compared']
        calc = self._calc_ratio if self.ratio_diffs else self._calc_diff
        for name, areas in mismatched.items():
            stats.append((calc(areas), name, self.basepath, areas[0], areas[1]))

    def find_rendered_diffs(self, font_size=128, render_path=None):
        """Find diffs of glyphs as rendered by harfbuzz."""

        hb_input_generator_a = hb_input.HbInputGenerator(self.font_a)
        hb_input_generator_b = hb_input.HbInputGenerator(self.font_b)

        if render_path:
            font_name, _ = os.path.splitext(self.basepath)
            render_path = os.path.join(render_path, font_name)
            if not os.path.exists(render_path):
                os.makedirs(render_path)

        self.build_names()
        diffs = []
        for name in self.names:
            class_a = self.gdef_a.get(name, GDEF_UNDEF)
            class_b = self.gdef_b.get(name, GDEF_UNDEF)
            if GDEF_MARK in (class_a, class_b) and class_a != class_b:
                self.stats['gdef_mark_mismatch'].append((
                    self.basepath, name, GDEF_LABELS[class_a],
                    GDEF_LABELS[class_b]))
                continue

            width_a = self.glyph_set_a[name].width
            width_b = self.glyph_set_b[name].width
            zwidth_a = width_a == 0
            zwidth_b = width_b == 0
            if zwidth_a != zwidth_b:
                self.stats['zero_width_mismatch'].append((
                    self.basepath, name, width_a, width_b))
                continue

            hb_args_a = hb_input_generator_a.input_from_name(name, pad=zwidth_a)
            hb_args_b = hb_input_generator_b.input_from_name(name, pad=zwidth_b)
            if hb_args_a != hb_args_b:
                self.stats['input_mismatch'].append((
                    self.basepath, name, hb_args_a, hb_args_b))
                continue

            # ignore unreachable characters
            if not hb_args_a:
                self.stats['untested'].append((self.basepath, name))
                continue

            features, text = hb_args_a

            # ignore null character
            if unichr(0) in text:
                continue

            img_file_a = StringIO.StringIO(subprocess.check_output([
                'hb-view', '--font-size=%d' % font_size,
                '--features=%s' % ','.join(features), self.path_a, text]))
            img_file_b = StringIO.StringIO(subprocess.check_output([
                'hb-view', '--font-size=%d' % font_size,
                '--features=%s' % ','.join(features), self.path_b, text]))
            img_a = Image.open(img_file_a)
            img_b = Image.open(img_file_b)
            width_a, height_a = img_a.size
            width_b, height_b = img_b.size
            data_a = img_a.getdata()
            data_b = img_b.getdata()
            img_file_a.close()
            img_file_b.close()

            width, height = max(width_a, width_b), max(height_a, height_b)
            offset_ax = (width - width_a) // 2
            offset_ay = (height - height_a) // 2
            offset_bx = (width - width_b) // 2
            offset_by = (height - height_b) // 2

            diff = 0
            for y in range(height):
                for x in range(width):
                    ax, ay = x - offset_ax, y - offset_ay
                    bx, by = x - offset_bx, y - offset_by
                    if (ax < 0 or bx < 0 or ax >= width_a or bx >= width_b or
                        ay < 0 or by < 0 or ay >= height_a or by >= height_b):
                        diff += 1
                    else:
                        diff += abs(data_a[ax + ay * width_a] -
                                    data_b[bx + by * width_b]) / 255

            if self.ratio_diffs:
                diff /= (width * height)

            if render_path and diff > self.diff_threshold:
                img_cmp = Image.new('RGB', (width, height))
                data_cmp = list(img_cmp.getdata())
                self._project(data_a, width_a, height_a,
                              data_cmp, width, height, 1)
                self._project(data_b, width_b, height_b,
                              data_cmp, width, height, 0)
                for y in range(height):
                    for x in range(width):
                        i = x + y * width
                        r, g, b = data_cmp[i]
                        assert b == 0
                        data_cmp[i] = r, g, min(r, g)
                img_cmp.putdata(data_cmp)
                img_cmp.save(self._rendered_png(render_path, name))

            diffs.append((name, diff))

        mismatched = {}
        for name, diff in diffs:
            if diff > self.diff_threshold:
                mismatched[name] = diff

        stats = self.stats['compared']
        for name, diff in mismatched.items():
            stats.append((diff, name, self.basepath))

    def _project(
            self, src_data, src_width, src_height,
            dst_data, width, height, channel):
        """Project a single-channel image onto a channel of an RGB image."""

        offset_x = (width - src_width) // 2
        offset_y = (height - src_height) // 2
        for y in range(src_height):
            for x in range(src_width):
                src_i = x + y * src_width
                dst_i = x + offset_x + (y + offset_y) * width
                pixel = list(dst_data[dst_i])
                pixel[channel] = src_data[src_i]
                dst_data[dst_i] = tuple(pixel)

    def find_shape_diffs(self):
        """Report differences in glyph shapes, using BooleanOperations."""

        self.build_names()

        area_pen = GlyphAreaPen(None)
        pen = PointToSegmentPen(area_pen)
        mismatched = {}
        for name in self.names:
            glyph_a = Glyph()
            glyph_b = Glyph()
            self.glyph_set_a[name].draw(
                Qu2CuPen(glyph_a.getPen(), self.glyph_set_a))
            self.glyph_set_b[name].draw(
                Qu2CuPen(glyph_b.getPen(), self.glyph_set_b))
            booleanOperations.xor(list(glyph_a), list(glyph_b), pen)
            area = abs(area_pen.pop())
            if area:
                mismatched[name] = (area)

        stats = self.stats['compared']
        for name, area in mismatched.items():
            stats.append((area, name, self.basepath))

    def find_area_shape_diff_products(self):
        """Report product of differences in glyph areas and glyph shapes."""

        self.find_area_diffs()
        old_compared = self.stats['compared']
        self.stats['compared'] = []
        self.find_shape_diffs()
        new_compared = {n: d for d, n, _ in self.stats['compared']}
        for i, (diff, name, font, area_a, area_b) in enumerate(old_compared):
            if font != self.basepath:
                continue
            new_diff = diff * new_compared.get(name, 0)
            old_compared[i] = new_diff, name, font, area_a, area_b
        self.stats['compared'] = old_compared

    def build_names(self):
        """Build a list of glyph names shared between the fonts."""

        if hasattr(self, 'names'):
            return

        stats = self.stats['unmatched']
        names_a = set(self.font_a.getGlyphOrder())
        names_b = set(self.font_b.getGlyphOrder())
        if names_a != names_b:
            stats.append((self.basepath, names_a - names_b, names_b - names_a))
        self.names = names_a & names_b

        stats = self.stats['unicode_mismatch']
        reverse_cmap_a = hb_input.build_reverse_cmap(self.font_a)
        reverse_cmap_b = hb_input.build_reverse_cmap(self.font_b)
        mismatched = {}
        for name in self.names:
            unival_a = reverse_cmap_a.get(name)
            unival_b = reverse_cmap_b.get(name)
            if unival_a != unival_b:
                mismatched[name] = (unival_a, unival_b)
        if mismatched:
            stats.append((self.basepath, mismatched.items()))
            self.names -= set(mismatched.keys())

    @staticmethod
    def dump(stats, whitelist, out_lines, include_vals, multiple_fonts):
        """Return the results of run diffs.

        Args:
            stats: List of tuples with diff data which is sorted and printed.
            whitelist: Names of glyphs to exclude from report.
            out_lines: Number of diff lines to print.
            include_vals: Include the values that have been diffed in report.
            multiple_fonts: Designates whether stats have been accumulated from
                multiple fonts, if so then font names will be printed as well.
        """

        report = []

        compared = sorted(
            s for s in stats['compared'] if s[1] not in whitelist)
        compared.reverse()
        fmt = '%s %s'
        if include_vals:
            fmt += ' (%s vs %s)'
        if multiple_fonts:
            fmt = '%s ' + fmt
        report.append('%d differences in glyph shape' % len(compared))
        for line in compared[:out_lines]:
            # print <font> <glyph> <vals>; stats are sorted in reverse priority
            line = tuple(reversed(line[:3])) + tuple(line[3:])
            # ignore font name if just one pair of fonts was compared
            if not multiple_fonts:
                line = line[1:]
            report.append(fmt % line)
        report.append('')

        for font, set_a, set_b in stats['unmatched']:
            report.append("Glyph coverage doesn't match in %s" % font)
            report.append('  in A but not B: %s' % sorted(set_a))
            report.append('  in B but not A: %s' % sorted(set_b))
        report.append('')

        for font, mismatches in stats['unicode_mismatch']:
            report.append("Glyph unicode values don't match in %s" % font)
            for name, univals in sorted(mismatches):
                univals = [(('0x%04X' % v) if v else str(v)) for v in univals]
                report.append('  %s: %s in A, %s in B' %
                              (name, univals[0], univals[1]))
        report.append('')

        ShapeDiffFinder._add_simple_report(
            report, stats['gdef_mark_mismatch'],
            '%s: Mark class mismatch for %s (%s vs %s)')
        ShapeDiffFinder._add_simple_report(
            report, stats['zero_width_mismatch'],
            '%s: Zero-width mismatch for %s (%d vs %d)')
        ShapeDiffFinder._add_simple_report(
            report, stats['input_mismatch'],
            '%s: Harfbuzz input mismatch for %s (%s vs %s)')
        ShapeDiffFinder._add_simple_report(
            report, stats['untested'],
            '%s: %s not tested (unreachable?)')

        return '\n'.join(report)

    @staticmethod
    def _add_simple_report(report, stats, fmt):
        for stat in sorted(stats):
            report.append(fmt % stat)
        if stats:
            report.append('')

    def _calc_diff(self, vals):
        """Calculate an area difference."""

        a, b = vals
        return abs(a - b)

    def _calc_ratio(self, vals):
        """Calculate an area ratio."""

        a, b = vals
        if not (a or b):
            return 0
        if abs(a) > abs(b):
            a, b = b, a
        return 1 - a / b

    def _rendered_png(self, render_path, glyph_name):
        glyph_filename = re.sub(r'([A-Z_])', r'\1_', glyph_name) + '.png'
        return os.path.join(render_path, glyph_filename)


class Qu2CuPen(BasePen):
    def __init__(self, pen, glyphSet):
        BasePen.__init__(self, glyphSet)
        self.pen = pen

    def _moveTo(self, pt):
        self.pen.moveTo(pt)

    def _lineTo(self, pt):
        self.pen.lineTo(pt)

    def _curveToOne(self, pt1, pt2, pt3):
        self.pen.curveTo(pt1, pt2, pt3)

    def _closePath(self):
        self.pen.closePath()

    def _endPath(self):
        self.pen.endPath()
