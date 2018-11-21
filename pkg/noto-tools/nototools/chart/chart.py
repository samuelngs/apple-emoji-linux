#!/usr/bin/python

import sys
import cairo
import pycairoft
from fontTools import ttLib

def clamp(x, Min, Max):
	return max(Min, min(Max, x))

class Color:

	def __init__(self, rgb):
		self.rgb = rgb

	def __repr__(self):
		return 'Color(%g,%g,%g)' % self.rgb

	def __str__(self):
		return "#%02X%02X%02X" % tuple(int(255 * c) for c in self.rgb)

class Font:

	def __init__(self, fontfile):
		self.filename = fontfile
		self.ttfont = ttLib.TTFont(fontfile)
		cmap = self.ttfont['cmap']
		self.charset = set()
		self.charset.update(*[t.cmap.keys() for t in cmap.tables if t.isUnicode()])
		self.cairo_font_face = None

	def get_cairo_font_face(self):
		if self.cairo_font_face is None:
			self.cairo_font_face = pycairoft.create_cairo_font_face_for_file (
						self.filename)
		return self.cairo_font_face


	def __repr__(self):
		return 'Font("%s")' % self.filename

def assign_colors(fonts):
	import colorsys
	n = len(fonts)
	mult = (n-1) // 2
	darkness = .3
	for i,font in enumerate(fonts):
		pos = (i * mult / float(n)) % 1.
		rgb = colorsys.hsv_to_rgb(pos, 1., darkness)
		luma = .3*rgb[0] + .59*rgb[1] + .11*rgb[2]
		adj = .3 - luma
		rgb = [c+adj for c in rgb]
		font.color = Color(rgb)

outfile = sys.argv[1]
fonts = [Font(fontfile) for fontfile in sys.argv[2:]]
charset = set.union(*[f.charset for f in fonts])
assign_colors(fonts)

coverage = {c:[] for c in charset}
for font in fonts:
	for char in font.charset:
		coverage[char].append(font)

NUM_COLS = 128
FONT_SIZE = 5
PADDING = 0.3
BOX_WIDTH = PADDING * .6
CELL_SIZE = FONT_SIZE + 2 * PADDING
MARGIN = 1 * FONT_SIZE
LABEL_WIDTH = 8 * FONT_SIZE/2.

rows = set([u // NUM_COLS * NUM_COLS for u in charset])
num_rows = len(rows)

width  = NUM_COLS * CELL_SIZE + 2 * (2 * MARGIN + LABEL_WIDTH)
height = num_rows * CELL_SIZE + 2 * MARGIN

print "Generating %s at %.3gx%.3gin" % (outfile, width/72., height/72.)
if outfile.endswith(".pdf"):
	surface = cairo.PDFSurface(outfile, width, height)
elif outfile.endswith(".ps"):
	surface = cairo.PSSurface(outfile, width, height)
else:
	assert 0
cr = cairo.Context(surface)
noto_sans_lgc = pycairoft.create_cairo_font_face_for_file ("../../fonts/individual/unhinted/NotoSans-Regular.ttf")

#cr.select_font_face("@cairo:", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

cr.set_font_size(FONT_SIZE)
cr.set_line_width(PADDING)

STAGE_BOXES = 0
STAGE_GLYPHS = 1
for stage in range(2):
	cr.save()
	cr.translate(MARGIN, MARGIN)
	for row,row_start in enumerate(sorted(rows)):
		cr.translate(0, PADDING)
		cr.save()

		cr.set_source_rgb(0,0,0)
		cr.move_to(0,FONT_SIZE)
		if stage == 0:
			cr.set_font_face(noto_sans_lgc)
			cr.show_text ("U+%04X" % row_start)
		cr.translate(LABEL_WIDTH + MARGIN, 0)
		for char in range(row_start, row_start + NUM_COLS):
			cr.translate(PADDING, 0)
			for font in coverage.get(char, []):
				if stage == STAGE_BOXES:
					#cr.rectangle(-BOX_WIDTH*.5, -BOX_WIDTH*.5, FONT_SIZE+BOX_WIDTH, FONT_SIZE+BOX_WIDTH)
					#cr.set_source_rgba(*[c * .1 + .9 for c in font.color.rgb])
					#cr.stroke()
					pass
				elif stage == STAGE_GLYPHS:
					cr.set_source_rgb(*(font.color.rgb))
					#cr.set_source_rgb(0,0,0)
					cr.set_font_face(font.get_cairo_font_face())
					ascent,descent,font_height,max_x_adv,max_y_adv = cr.font_extents()

					cr.save()
					# XXX cr.set_font_size (FONT_SIZE*FONT_SIZE / (ascent+descent))
					cr.set_font_size (round(1.2 * FONT_SIZE*FONT_SIZE / (ascent+descent)))

					ascent,descent,font_height,max_x_adv,max_y_adv = cr.font_extents()
					utf8 = unichr(char).encode('utf-8')
					x1,y1,width,height,xadv,yadv = cr.text_extents(utf8)
					cr.move_to(FONT_SIZE*.5 - (x1+.5*width),
						   FONT_SIZE*.5 - (-ascent+descent)*.5)
					cr.show_text(utf8)

					cr.restore()
				break
			cr.translate(FONT_SIZE, 0)
			cr.translate(PADDING, 0)
		cr.set_source_rgb(0,0,0)
		cr.move_to(MARGIN,FONT_SIZE)
		if stage == 0:
			cr.set_font_face(noto_sans_lgc)
			cr.show_text ("U+%04X" % (row_start + NUM_COLS - 1))
		cr.translate(LABEL_WIDTH + 2 * MARGIN, 0)

		cr.restore()
		cr.translate(0, FONT_SIZE)
		cr.translate(0, PADDING)
	cr.restore()
