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

EMOJI = AppleColorEmoji
font: $(EMOJI).ttf

CFLAGS = -std=c99 -Wall -Wextra `pkg-config --cflags --libs cairo`
LDFLAGS = -lm `pkg-config --libs cairo`

PNGQUANT = pngquant
PYTHON = python3
PNGQUANTFLAGS = --speed 1 --skip-if-larger --quality 85-95 --force
BODY_DIMENSIONS = 136x128
IMOPS := -size $(BODY_DIMENSIONS) canvas:none -compose copy -gravity center

# zopflipng is better (about 5-10%) but much slower.  it will be used if
# present.  pass ZOPFLIPNG= as an arg to make to use optipng instead.

ZOPFLIPNG = zopflipng
OPTIPNG = optipng

EMOJI_BUILDER = third_party/color_emoji/emoji_builder.py
# flag for emoji builder.  Default to legacy small metrics for the time being.
SMALL_METRICS := -S
ADD_GLYPHS = add_glyphs.py
ADD_GLYPHS_FLAGS = -a emoji_aliases.txt
PUA_ADDER = map_pua_emoji.py
VS_ADDER = add_vs_cmap.py # from nototools

EMOJI_SRC_DIR ?= png/128

BUILD_DIR := build
EMOJI_DIR := $(BUILD_DIR)/emoji
QUANTIZED_DIR := $(BUILD_DIR)/quantized_pngs
COMPRESSED_DIR := $(BUILD_DIR)/compressed_pngs

EMOJI_NAMES = $(notdir $(wildcard $(EMOJI_SRC_DIR)/emoji_u*.png))
EMOJI_FILES= $(addprefix $(EMOJI_DIR)/,$(EMOJI_NAMES)))

ALL_NAMES = $(EMOJI_NAMES)

ALL_QUANTIZED_FILES = $(addprefix $(QUANTIZED_DIR)/, $(ALL_NAMES))
ALL_COMPRESSED_FILES = $(addprefix $(COMPRESSED_DIR)/, $(ALL_NAMES))

# tool checks
ifeq (,$(shell which $(ZOPFLIPNG)))
  ifeq (,$(wildcard $(ZOPFLIPNG)))
    MISSING_ZOPFLI = fail
  endif
endif

ifeq (,$(shell which $(OPTIPNG)))
  ifeq (,$(wildcard $(OPTIPNG)))
    MISSING_OPTIPNG = fail
  endif
endif

ifeq (, $(shell which $(VS_ADDER)))
  MISSING_ADDER = fail
endif


emoji: $(EMOJI_FILES)

quantized: $(ALL_QUANTIZED_FILES)

compressed: $(ALL_COMPRESSED_FILES)

check_compress_tool:
ifdef MISSING_ZOPFLI
  ifdef MISSING_OPTIPNG
	$(error "neither $(ZOPFLIPNG) nor $(OPTIPNG) is available")
  else
	@echo "using $(OPTIPNG)"
  endif
else
	@echo "using $(ZOPFLIPNG)"
endif

check_vs_adder:
ifdef MISSING_ADDER
	$(error "$(VS_ADDER) not in path, run setup.py in nototools")
endif


$(EMOJI_DIR) $(QUANTIZED_DIR) $(COMPRESSED_DIR):
	mkdir -p "$@"


# imagemagick's -extent operator munges the grayscale images in such a fashion
# that while it can display them correctly using libpng12, chrome and gimp using
# both libpng12 and libpng16 display the wrong gray levels.
#
# @convert "$<" -gravity center -background none -extent 136x128 "$@"
#
# We can get around the conversion to a gray colorspace in the version of
# imagemagick packaged with ubuntu trusty (6.7.7-10) by using -composite.

$(EMOJI_DIR)/%.png: $(EMOJI_SRC_DIR)/%.png | $(EMOJI_DIR)
	@convert $(IMOPS) "$<" -composite "PNG32:$@"

$(QUANTIZED_DIR)/%.png: $(EMOJI_DIR)/%.png | $(QUANTIZED_DIR)
	@($(PNGQUANT) $(PNGQUANTFLAGS) -o "$@" "$<"; case "$$?" in "98"|"99") echo "reuse $<";cp $< $@;; *) exit "$$?";; esac)

$(COMPRESSED_DIR)/%.png: $(QUANTIZED_DIR)/%.png | check_compress_tool $(COMPRESSED_DIR)
ifdef MISSING_ZOPFLI
	@$(OPTIPNG) -quiet -o7 -clobber -force -out "$@" "$<"
else
	@$(ZOPFLIPNG) -y "$<" "$@" 1> /dev/null 2>&1
endif


# Make 3.81 can endless loop here if the target is missing but no
# prerequisite is updated and make has been invoked with -j, e.g.:
# File `font' does not exist.
#      File `AppleColorEmoji.tmpl.ttx' does not exist.
# File `font' does not exist.
#      File `AppleColorEmoji.tmpl.ttx' does not exist.
# ...
# Run make without -j if this happens.

%.ttx: %.ttx.tmpl $(ADD_GLYPHS) $(ALL_COMPRESSED_FILES)
	@$(PYTHON) $(ADD_GLYPHS) -f "$<" -o "$@" -d "$(COMPRESSED_DIR)" $(ADD_GLYPHS_FLAGS)

%.ttf: %.ttx
	@rm -f "$@"
	ttx "$<"

$(EMOJI).ttf: $(EMOJI).tmpl.ttf $(EMOJI_BUILDER) $(PUA_ADDER) \
	$(ALL_COMPRESSED_FILES) | check_vs_adder
	@$(PYTHON) $(EMOJI_BUILDER) $(SMALL_METRICS) -V $< "$@" "$(COMPRESSED_DIR)/emoji_u"
	@$(PYTHON) $(PUA_ADDER) "$@" "$@-with-pua"
	@$(VS_ADDER) -vs 2640 2642 2695 --dstdir '.' -o "$@-with-pua-varsel" "$@-with-pua"
	@mv "$@-with-pua-varsel" "$@"
	@rm "$@-with-pua"

install: font
	mkdir -p $$HOME/.local/share/fonts
	cp -f AppleColorEmoji.ttf $$HOME/.local/share/fonts/

clean:
	rm -f $(EMOJI).ttf $(EMOJI).tmpl.ttf $(EMOJI).tmpl.ttx
	rm -rf $(BUILD_DIR)

.SECONDARY: $(EMOJI_FILES) $(ALL_QUANTIZED_FILES) $(ALL_COMPRESSED_FILES)

.PHONY:	clean compressed check_compress_tool emoji install quantized
