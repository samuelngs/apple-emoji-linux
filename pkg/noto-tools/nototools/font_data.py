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

"""Get high-level font data from a font object."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

from nototools import opentype_data

from fontTools.ttLib.tables._n_a_m_e import NameRecord

def get_name_records(font):
    """Get a font's 'name' table records as a dictionary of Unicode strings."""
    name_table = font['name']
    names = {}
    for record in name_table.names:
        name_ids = (record.platformID, record.platEncID, record.langID)
        if name_ids != (3, 1, 0x409):
            continue
        names[record.nameID] = unicode(record.string, 'UTF-16BE')
    return names


def set_name_record(font, record_id, value, addIfMissing=''):
    """Sets a record in the 'name' table to a given string.

    Assumes that the record already exists. If it doesn't, it only adds it
    if addIfMissing is set.  Pass 'win' to add a record in 3/1/0x409 (win UCS2 en-US)
    and/or 'mac' to add a record in 1/0/0 (mac-roman English), separate by comma
    if you want both.

    If 'value' is None, the name record is dropped."""
    records_to_drop = set()
    names = font['name'].names
    added = []
    for record_number, record in enumerate(names):
        name_ids = (record.platformID, record.platEncID, record.langID)
        if name_ids not in [(3, 1, 0x409), (1, 0, 0)]:
            continue
        if record.nameID == record_id:
            if value is None:
                records_to_drop.add(record_number)
            else:
                if name_ids == (1, 0, 0):
                    record.string = value.encode('mac-roman')
                    added.append('mac')
                else:  # (3, 1, 0x409)
                    record.string = value.encode('UTF-16BE')
                    added.append('win')

    if addIfMissing and value:
        for key in addIfMissing.split(','):
            if key in added:
                continue

            if key == 'win':
                nr = NameRecord()
                nr.nameID = record_id
                nr.platformID = 3
                nr.platEncID = 1
                nr.langID = 0x409
                nr.string = value.encode('UTF-16BE')
            elif key == 'mac':
                nr = NameRecord()
                nr.nameID = record_id
                nr.platformID = 1
                nr.platEncID = 0
                nr.langID = 0
                nr.string = value.encode('mac-roman')
            else:
                nr = None

            if nr:
                names.append(nr)

    if records_to_drop:
        font['name'].names = [
            record for record_number, record in enumerate(names)
            if record_number not in records_to_drop]


def get_os2_unicoderange_bitmap(font):
    """Get an integer bitmap representing the UnicodeRange fields in the os/2 table."""
    os2_table = font['OS/2']
    return (os2_table.ulUnicodeRange1 |
           os2_table.ulUnicodeRange2 << 32 |
           os2_table.ulUnicodeRange3 << 64 |
           os2_table.ulUnicodeRange4 << 96)


def set_os2_unicoderange_bitmap(font, bitmap):
    """Set the UnicodeRange fields in the os/2 table from the 128 bits of the
       long integer bitmap."""
    os2_table = font['OS/2']
    mask = (1 << 32) - 1
    os2_table.ulUnicodeRange1 = bitmap & mask
    os2_table.ulUnicodeRange2 = (bitmap >> 32) & mask
    os2_table.ulUnicodeRange3 = (bitmap >> 64) & mask
    os2_table.ulUnicodeRange4 = (bitmap >> 96) & mask


def get_cmap_unicoderange_info(font):
    """Get info on unicode ranges based on the cmap in the font."""
    cmap = get_cmap(font)
    return opentype_data.collect_unicoderange_info(cmap)


def unicoderange_info_to_bitmap(ur_info):
    # Turn on a bit (mark it functional) if any range for that bit
    # has more than 200 characters or is more than 50% covered.
    # Non-BMP (57) and private use (60, 90) are marked functional if
    # any character is set.
    #
    # This means, for example, that Cyrillic is marked functional
    # if any of Cyrillic, Cyrillic Supplement, or Cyrillic Extended A or B
    # have more than 50% coverage.  There's no really good heuristic
    # for this without explicit per-script data, we're really just
    # trying to catch obvious errors.

    expected_bitmap = 0L
    for count, info in ur_info:
        bit = info[2]
        # any non-bmp character causes bit 57 to be set
        if info[0] >= 0x10000:
            expected_bitmap |= 1 << 57
        if bit in [57, 60, 90] or count > min(200, (info[1] - info[0]) / 2):
            expected_bitmap |= 1 << bit
    return expected_bitmap


def get_cmap_unicoderange_bitmap(font):
    return unicoderange_info_to_bitmap(get_cmap_unicoderange_info(font))


def unicoderange_bitmap_to_string(bitmap):
    have_list = []
    for bucket_index in range(128):
        if bitmap & (1 << bucket_index):
            bucket_name = opentype_data.unicoderange_bucket_index_to_name(bucket_index)
            have_list.append("%d (%s)" % (bucket_index, bucket_name))
    return '; '.join(have_list)


def font_version(font):
    """Returns the font version from the 'name' table."""
    names = get_name_records(font)
    return names[5]


def font_name(font):
    """Returns the font name from the 'name' table."""
    names = get_name_records(font)
    return names[4]


def printable_font_revision(font, accuracy=2):
    """Returns the font revision as a string from the 'head' table."""
    font_revision = font['head'].fontRevision
    font_revision_int = int(font_revision)
    font_revision_frac = int(
        round((font_revision - font_revision_int) * 10**accuracy))

    font_revision_int = str(font_revision_int)
    font_revision_frac = str(font_revision_frac).zfill(accuracy)
    return font_revision_int+'.'+font_revision_frac


def get_cmap(font):
    """Get the cmap dictionary of a font."""
    cmap_table = font['cmap']
    cmaps = {}
    for table in cmap_table.tables:
        if (table.format, table.platformID, table.platEncID) in [
            (4, 3, 1), (12, 3, 10)]:
            cmaps[table.format] = table.cmap
    if 12 in cmaps:
        return cmaps[12]
    elif 4 in cmaps:
        return cmaps[4]
    return {}


def get_variation_sequence_cmap(font):
    """Return the variation selector cmap, if available."""
    cmap_table = font['cmap']
    for table in cmap_table.tables:
        if table.format == 14:
            return table
    return None


UNICODE_CMAPS = {(4, 0, 3), (4, 3, 1), (12, 3, 10)}

def delete_from_cmap(font, chars):
    """Delete all characters in a list from the cmap tables of a font."""
    cmap_table = font['cmap']
    for table in cmap_table.tables:
        if (table.format, table.platformID, table.platEncID) in UNICODE_CMAPS:
            for char in chars:
                if char in table.cmap:
                    del table.cmap[char]


def add_to_cmap(font, mapping):
    """Adds a codepoint to glyph mapping to a font's cmap."""
    cmap_table = font['cmap']
    for table in cmap_table.tables:
        if (table.format, table.platformID, table.platEncID) in UNICODE_CMAPS:
            for code, glyph in mapping.iteritems():
                table.cmap[code] = glyph


def get_glyph_horizontal_advance(font, glyph_id):
    """Returns the horiz advance of the glyph id."""
    hmtx_table = font['hmtx'].metrics
    adv, lsb = hmtx_table[glyph_id]
    return adv
