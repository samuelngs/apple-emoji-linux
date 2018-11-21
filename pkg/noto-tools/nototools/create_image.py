#!/usr/bin/env python
# -*- coding: utf-8-unix -*-
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

"""Create sample images given a font and text."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import argparse
import codecs
import os
from os import path
import string

from nototools import notoconfig

import cairo
import pango
import pangocairo

_fonts_conf_template = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  ${font_dirs}

  <include>/etc/fonts/conf.d</include>

  <match target="scan">
    <test name="family">
       <string>Noto Color Emoji</string>
    </test>
    <edit name="scalable" mode="assign"><bool>true</bool></edit>
  </match>

  <cachedir>${cache_dir}</cachedir>
</fontconfig>
"""

def setup_fonts_conf():
  """We first look for fonts.conf under the root nototools, and if we don't
  find it we write it.  The fontconfig cache also goes there.  This of course
  requires nototools to be writable."""

  # We require notoconfig because we don't know where this code is located,
  # nor whether the font directories might be relative to it.

  TOOLS_DIR = notoconfig.noto_tools()
  fonts_conf = path.join(TOOLS_DIR, 'fonts.conf')
  if not path.isfile(fonts_conf):
    noto_font_dirs = []
    FONTS_DIR = notoconfig.noto_fonts()
    if FONTS_DIR:
      noto_font_dirs.extend(
          [path.join(FONTS_DIR, 'hinted'), path.join(FONTS_DIR, 'unhinted')])
    CJK_DIR = notoconfig.noto_cjk()
    if CJK_DIR:
      noto_font_dirs.append(CJK_DIR)
    EMOJI_DIR = notoconfig.noto_emoji()
    if EMOJI_DIR:
      noto_font_dirs.append(path.join(EMOJI_DIR, 'fonts'))
    font_dirs = '\n  '.join('<dir>%s</dir>' % d for d in noto_font_dirs)

    cache_dir = path.join(TOOLS_DIR, 'fontconfig')
    template = string.Template(_fonts_conf_template)
    conf_text = template.substitute(font_dirs=font_dirs, cache_dir=cache_dir)
    try:
      with open(fonts_conf, 'w') as f:
        f.write(conf_text)
    except IOError as e:
      raise Exception('unable to write %s: %s' % (fonts_conf, e))

  # Note: ensure /etc/fonts/conf.d/10-scale-bitmap-fonts.conf is
  # in sync with fontconfig to make sure color emoji font scales properly.
  os.putenv('FONTCONFIG_FILE', fonts_conf)


class DrawParams:
    """Parameters used for rendering text in draw_on_surface and its callers"""

    def __init__(self, family='Noto Sans',
                 language=None, rtl=False, vertical=False,
                 width=1370, font_size=32, line_spacing=50,
                 weight=pango.WEIGHT_NORMAL, style=pango.STYLE_NORMAL,
                 stretch=pango.STRETCH_NORMAL, maxheight=0, horiz_margin=0):
        self.family = family
        self.language = language
        self.rtl = rtl
        self.vertical = vertical
        self.width = width
        self.font_size = font_size
        self.line_spacing = line_spacing
        self.weight = weight
        self.style = style
        self.stretch = stretch
        self.maxheight = maxheight
        self.horiz_margin = horiz_margin

    def __repr__(self):
        return str(self.__dict__)


def make_drawparams(**kwargs):
  """Create a DrawParams from kwargs, but converting weight, style, and stretch
  from values from string to the pango value types if needed."""
  dp = DrawParams(**kwargs)
  dp.weight = _get_weight(kwargs.get('weight', 'normal'))
  dp.style = _get_style(kwargs.get('style', 'normal'))
  dp.stretch = _get_stretch(kwargs.get('stretch', 'normal'))
  return dp


def draw_on_surface(surface, text, params):
    """Draw the string on a pre-created surface and return height."""
    pangocairo_ctx = pangocairo.CairoContext(cairo.Context(surface))
    layout = pangocairo_ctx.create_layout()

    pango_ctx = layout.get_context()
    if params.language is not None:
        pango_ctx.set_language(pango.Language(params.language))

    if params.rtl:
        if params.vertical:
            base_dir = pango.DIRECTION_TTB_RTL
        else:
            base_dir = pango.DIRECTION_RTL
        alignment = pango.ALIGN_RIGHT
    else:
        if params.vertical:
            base_dir = pango.DIRECTION_TTB_LTR
        else:
            base_dir = pango.DIRECTION_LTR
        alignment = pango.ALIGN_LEFT

    # The actual meaning of alignment is confusing.
    #
    # In an RTL context, RTL text aligns to the right by default.  So
    # setting right alignment and an RTL context means asking for
    # 'default alignment' (just as does setting left alignment and an
    # LTR context).
    #
    # What actually happens depends on the directionality of the actual
    # text in the paragraph. If the text is Arabic this will be RTL, so
    # it is aligned to the right, the default alignment for RTL text.
    # And if the text is English this will be LTR, so it is aligned to
    # the left, the default alignment for LTR text.
    #
    # This is reversed when the context and the alignment disagree:
    # setting left alignment in an RTL context (or right alignment in an
    # LTR context) means asking for 'opposite alignment'.  Arabic text
    # is aligned to the left, and English text to the right.
    #
    # pango layout set_auto_dir controls whether the text direction
    # is based on the text itself, or influenced by the context.  By
    # default it is off so the text direction is completely independent
    # of the setting of the context: Arabic text is RTL and English text
    # is LTR.  However, the algorithm depends on the first 'strongly
    # directional' character encountered in a paragraph.  If you have
    # text that is largly Arabic but happens to start with English
    # (e.g. brand names) it will be assigned LTR, the wrong direction.
    # Either you force the correct direction by munging the text or you
    # tell pango to use the context.
    #
    # The text will be reordered based on the unicode bidi attributes
    # of the characters, and this is only as good as your unicode data.
    # Newly-encoded scripts can be newer than your libraries and will
    # likely order LTR if you implementation doesn't know about them.

    # The width is the desired width of the image.  The layout uses this
    # width minus the margin.
    width = params.width - 2 * params.horiz_margin

    font = pango.FontDescription()
    font.set_family(params.family)
    font.set_size(params.font_size * pango.SCALE)
    font.set_style(params.style)
    font.set_weight(params.weight)
    font.set_stretch(params.stretch)

    layout.set_font_description(font)
    layout.set_alignment(alignment)
    layout.set_width(width * pango.SCALE)
    layout.set_wrap(pango.WRAP_WORD_CHAR)
    layout.set_spacing((params.line_spacing - params.font_size) * pango.SCALE)
    pango_ctx.set_base_dir(base_dir)
    layout.context_changed()
    layout.set_text(text)

    if params.maxheight:
      numlines = layout.get_line_count()
      if params.maxheight < 0:
        if -params.maxheight < numlines:
          startindex = layout.get_line_readonly(-params.maxheight).start_index
          layout.set_text(text[:startindex])
      else:
        ht = 0
        for i in range(numlines):
          line = layout.get_line_readonly(i)
          lrect = line.get_extents()[1]  # logical bounds
          lh = (-lrect[1] + lrect[3]) / pango.SCALE
          ht += lh
          if ht > params.maxheight and i > 0:
            layout.set_text(text[:line.start_index])
            break

    extents = layout.get_pixel_extents()
    ovl = -extents[0][0] > params.horiz_margin
    ovr = extents[0][2] > width + params.horiz_margin
    if ovl or ovr:
      if ovl:
        print 'Error: image overflows left bounds'
      if ovr:
        print 'Error: image overflows right bounds'
      print 'extents: %s, width: %s, margin: %s' % (
          extents, params.width, params.horiz_margin)
    top_usage = min(extents[0][1], extents[1][1], 0)
    bottom_usage = max(extents[0][3], extents[1][3])

    pangocairo_ctx.set_antialias(cairo.ANTIALIAS_GRAY)
    pangocairo_ctx.set_source_rgb(1, 1, 1)  # White background
    pangocairo_ctx.paint()

    pangocairo_ctx.translate(params.horiz_margin, -top_usage)
    pangocairo_ctx.set_source_rgb(0, 0, 0)  # Black text color
    pangocairo_ctx.show_layout(layout)

    return bottom_usage - top_usage


def create_svg(text, output_path, **kwargs):
    """Creates an SVG image from the given text."""

    setup_fonts_conf()

    params = make_drawparams(**kwargs);
    temp_surface = cairo.SVGSurface(None, 0, 0)
    calculated_height = draw_on_surface(temp_surface, text, params)

    real_surface = cairo.SVGSurface(
        output_path, params.width, calculated_height)
    print 'writing', output_path
    draw_on_surface(real_surface, text, params)
    real_surface.flush()
    real_surface.finish()


def create_png(text, output_path, **kwargs):
    """Creates a PNG image from the given text."""

    setup_fonts_conf()

    params = make_drawparams(**kwargs);
    temp_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 0, 0)
    calculated_height = draw_on_surface(temp_surface, text, params)

    real_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
        params.width, calculated_height)
    draw_on_surface(real_surface, text, params)
    print 'writing', output_path
    real_surface.write_to_png(output_path)


def create_img(text, output_path, **kwargs):
    """Creates a PNG or SVG image based on the output_path extension,
       from the given text"""
    ext = (path.splitext(output_path)[1]).lower()
    if ext == '.png':
        create_png(text, output_path, **kwargs)
    elif ext == '.svg':
        create_svg(text, output_path, **kwargs)
    else:
        print 'extension % not supported' % ext


def test():
    """Test sample Hindi and Arabic texts."""

    def test(text_file, output_file, **kwargs):
        file_path = '../sample_texts/' + text_file
        with codecs.open(file_path, 'r', encoding='UTF-8') as input_file:
            sample_text = input_file.read().strip()
        create_img(sample_text, output_file, **kwargs)

    test('en-Latn_udhr.txt', 'en_latn_udhr.svg', family='Noto Serif Display',
         maxheight=-2, font_size=80, line_spacing=96, style='italic',
         horiz_margin=16)
    """
    test('hi-Deva_udhr.txt', 'hindi.png', family='Noto Sans',
         language='hi-Deva')
    test('ar-Arab_udhr.txt', 'arabic.svg', family='Noto Naskh Arabic',
         language='ar', rtl=True)
    test('mn-Mong_udhr.txt', 'mong.png', family='Noto Sans',
         language='mn', vertical=True)
    test('sr-Cyrl_udhr.txt', 'sr_cyrl.png', family='Noto Sans',
         language='sr-Cyrl')
    test('und-Adlm_chars.txt', 'und-adlm.png', family='Noto Sans',
         rtl=True)
    test('en-Latn_udhr.txt', 'en_latn_udhr_semcond.svg', family='Noto Sans',
         stretch='semi-condensed')
    test('en-Latn_udhr.txt', 'en_latn_udhr_cond.svg', family='Noto Sans',
         stretch='condensed')
    test('en-Latn_udhr.txt', 'en_latn_udhr_extcond.svg', family='Noto Sans',
         stretch=pango.STRETCH_EXTRA_CONDENSED)
    """

    # test('en-Latn_udhr.txt', 'en_latn_rtl.png', family='Noto Sans', rtl=True)
    # bidi_txt = u'First ضميرً Second'
    # create_img(bidi_txt, 'bidi.png', family='Noto Sans', rtl=True)


_weight_map = {
    'ultralight': pango.WEIGHT_ULTRALIGHT,
    'light': pango.WEIGHT_LIGHT,
    'normal': pango.WEIGHT_NORMAL,
    'bold': pango.WEIGHT_BOLD,
    'ultrabold': pango.WEIGHT_ULTRABOLD,
    'heavy': pango.WEIGHT_HEAVY
  }

def _get_weight(weight_name):
  if not weight_name:
    return pango.WEIGHT_NORMAL
  if isinstance(weight_name, pango.Weight) or isinstance(weight_name, int):
    return weight_name
  if not isinstance(weight_name, basestring):
    raise ValueError('unexpected weight name type (%s)', type(weight_name))
  if weight_name not in _weight_map:
    raise ValueError(
        'could not recognize weight \'%s\'\naccepted values are %s' % (
            weight_name, ', '.join(sorted(_weight_map.keys()))))
  return _weight_map.get(weight_name)


_italic_map = {
    'italic': pango.STYLE_ITALIC,
    'oblique': pango.STYLE_OBLIQUE,
    'normal': pango.STYLE_NORMAL
  }

def _get_style(style_name):
  if not style_name:
    return pango.STYLE_NORMAL
  if isinstance(style_name, pango.Style):
    return style_name
  if not isinstance(style_name, basestring):
    raise ValueError('unexpected style name type (%s)', type(style_name))
  if style_name not in _italic_map:
    raise ValueError(
        'could not recognize style \'%s\'\naccepted values are %s' % (
            style_name, ', '.join(sorted(_italic_map.keys()))))
  return _italic_map.get(style_name)


_stretch_map = {
    'ultra-condensed': pango.STRETCH_ULTRA_CONDENSED,
    'extra-condensed': pango.STRETCH_EXTRA_CONDENSED,
    'condensed': pango.STRETCH_CONDENSED,
    'semi-condensed': pango.STRETCH_SEMI_CONDENSED,
    'normal': pango.STRETCH_NORMAL,
    'semi-expanded': pango.STRETCH_SEMI_EXPANDED,
    'expanded': pango.STRETCH_EXPANDED,
    'extra-expanded': pango.STRETCH_EXTRA_EXPANDED,
    'ultra-expanded': pango.STRETCH_ULTRA_EXPANDED,
}

def _get_stretch(stretch_name):
  if not stretch_name:
    return pango.STRETCH_NORMAL
  if isinstance(stretch_name, pango.Stretch):
    return stretch_name
  if not isinstance(stretch_name, basestring):
    raise ValueError('unexpected stretch name type (%s)', type(stretch_name))
  if stretch_name not in _stretch_map:
    raise ValueError(
        'could not recognize stretch \'%s\'\naccepted values are %s' % (
            stretch_name, ', '.join(sorted(_stretch_map.keys()))))
  return _stretch_map.get(stretch_name)


def render_codes(
    file_name, code_list, font_name, weight_name, style_name, stretch_name,
    font_size, lang, ext):
  text = u''.join([unichr(int(s, 16)) for s in code_list])
  render_text(
      file_name, text, font_name, weight_name, style_name, stretch_name,
      font_size, lang, ext)


def render_text(
    file_name, text, font_name, weight_name, style_name, stretch_name,
    font_size, lang, ext, maxheight=0, horiz_margin=0):
    font = font_name or 'Noto Sans'
    font_size = font_size or 32
    if not file_name:
      name_strs = [font.replace(' ', '')]
      name_strs.extend(['%x' % ord(cp) for cp in text])
      if weight_name:
        name_strs.append(weight_name)
      if style_name:
        name_strs.append(style_name)
      if stretch_name:
        name_strs.append(stretch_name)
      name_strs.append(str(font_size))
      if lang:
        name_strs.append(lang)
      file_name = '_'.join(name_strs) + '.' + ext

    create_img(
        text, file_name, family=font, weight=weight_name, style=style_name,
        stretch=stretch_name, language=lang, font_size=font_size,
        maxheight=maxheight, horiz_margin=horiz_margin)
    print 'generated ' + file_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--test', action='store_true', help='generate test images')
    parser.add_argument(
        '--codes', metavar='hex', nargs='+',
        help='list of hex codepoints to render')
    parser.add_argument(
        '--text', metavar='str',
        help='text to render, can include unicode escapes')
    parser.add_argument(
        '--out', metavar='name',
        help='name of output file, leave empty to generate a name',
        default=None)
    parser.add_argument(
        '-f', '--font', metavar='name', help='name of noto font to use')
    parser.add_argument(
        '-b', '--bold', metavar='wt', help="pango weight name", default=None)
    parser.add_argument(
        '-i', '--italic', metavar='it', help="pango style name", default=None)
    parser.add_argument(
        '-st', '--stretch', metavar='st', help="stretch name",
        default=None)
    parser.add_argument(
        '-s', '--size', metavar='int', type=int, help='point size (default 32)',
        default=32)
    parser.add_argument(
        '-l', '--lang', metavar='lang', help='language code')
    parser.add_argument(
        '-t', '--type', metavar='ext', help='svg (default) or png',
        default='svg')
    parser.add_argument(
        '-mh', '--maxheight', metavar='ht', help='0 ignore, <0 for num lines, '
        'else max height', default=0)
    parser.add_argument(
        '-hm', '--horiz_margin', metavar='mar', help='left and right margin, '
        'to handle large italic side bearings', default=0)

    args = parser.parse_args()
    if args.test:
      test()
      return
    if args.codes and args.text:
      print 'choose either codes or text'
      return
    if args.codes:
      render_codes(
          args.out, args.codes, args.font, args.bold, args.italic, args.size,
          args.lang, args.type, args.maxheight, args.horiz_margin)
    elif args.text:
      if args.text[0] == '@':
        if not args.out:
          args.out = path.splitext(args.text[1:])[0] + '.' + args.type
        with open(args.text[1:], 'r') as f:
          args.text = f.read()
      else:
        args.text = args.text.decode('unicode-escape')
      print 'text length %d' % len(args.text)
      render_text(
          args.out, args.text, args.font, args.bold, args.italic, args.size,
          args.lang, args.type, args.maxheight, args.horiz_margin)
    else:
      print 'nothing to do'


if __name__ == '__main__':
    main()
