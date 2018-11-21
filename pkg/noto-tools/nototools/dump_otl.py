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

"""Dumps the OpenType Layout tables in a font in a readable format."""

__author__ = "roozbeh@google.com (Roozbeh Pournader)"

import sys

from fontTools import ttLib


def internal_font_name(font):
    """Returns the font name according to the data in the name table."""
    name_table = font['name']
    for record in name_table.names:
        identifier = (record.nameID, record.platformID,
                      record.platEncID, record.langID)
        if identifier in [(4, 3, 1, 0x409), (4, 3, 0, 0x409)]:
            return unicode(record.string, 'UTF-16BE')


def print_indented(output_string, indents=1):
    """Prints a string indented with a specified number of spaces."""
    print '  ' * indents + output_string

def printable_glyph_class(glyph_list, quote=False):
    """Returns a printable form for a class of glyphs."""
    if quote:
        suffix = "'"
    else:
        suffix = ''

    if len(glyph_list) == 1:
        return list(glyph_list)[0]+suffix
    else:
        return '[' + ' '.join(glyph_list) + ']'+suffix
    

def printable_glyph_list(glyph_list, quote=False):
    """Returns a printable form for a list of glyphs."""
    if quote:
        suffix = "'"
    else:
        suffix = ''
    
    if len(glyph_list) == 1:
        return glyph_list[0]+suffix
    else:
        glyph_list = [glyph+suffix for glyph in glyph_list]
        return ' '.join(glyph_list)


def dump_lang_sys(script, lang, lang_sys):
    """Dumps a language system."""
    print '%s %s:' % (script, lang),
    assert lang_sys.LookupOrder is None
    if lang_sys.ReqFeatureIndex != 65535:
        print '<%s>' % lang_sys.ReqFeatureIndex,
    print lang_sys.FeatureIndex


def extract_glyphs_from_coverage(coverage):
    """Return a list of glyphs from a coverage."""
    if isinstance(coverage, str):
        return [coverage]
    else:
        return coverage.glyphs
    

def print_contextual_substitution(backtrack, center, lookahead, subs,
                                  reverse=False):
    """Prints out a contextual substitution rule."""
    if reverse:
        rule_name = 'rsub'
    else:
        rule_name = 'sub'
      
    if not subs:
        rule_name = 'ignore ' + rule_name
      
    output_list = []
    for coverage in center:
        glyphs = extract_glyphs_from_coverage(coverage)
        output_list.append(printable_glyph_class(glyphs, quote=True))

    if subs:
        if isinstance(subs[0], str):
            output_list.append('by')
            output_list.append(printable_glyph_class(subs))
        else:
            records_added = 0
            for record in subs:
                output_list.insert(
                    record.SequenceIndex + 1 + records_added,
                    'lookup %d' % record.LookupListIndex)
                records_added += 1
    
    for coverage in backtrack:
        glyphs = extract_glyphs_from_coverage(coverage)
        output_list.insert(0, printable_glyph_class(glyphs))
    for coverage in lookahead:
        glyphs = extract_glyphs_from_coverage(coverage)
        output_list.append(printable_glyph_class(glyphs))
    print_indented('%s %s;' % (rule_name, ' '.join(output_list)))


def dump_gsub_subtable(lookup_type, subtable):
    """Dumps a GSUB subtable."""
    if lookup_type == 7:
        # Extension. Decompile and pass down as another lookup type
        lookup_type = subtable.ExtensionLookupType
        print_indented('# (extension for %d)' % lookup_type)
        ext_sub_table = subtable.ExtSubTable
        subtable = ext_sub_table
        # Proceed to the actual type

    if lookup_type == 1:
        for key in sorted(subtable.mapping.keys()):
            print_indented('sub %s by %s;' % (key, subtable.mapping[key]))

    elif lookup_type == 2:
        for key, value in sorted(subtable.mapping.items()):
            print_indented('sub %s by %s;' % (key, ' '.join(value)))

    elif lookup_type == 3:
        for key in sorted(subtable.alternates.keys()):
            print_indented('sub %s from %s;' % (
                key,
                printable_glyph_class(subtable.alternates[key])))

    elif lookup_type == 4:
        for key in sorted(subtable.ligatures.keys()):
            for ligature in subtable.ligatures[key]:
                print_indented('sub %s by %s;' % (
                    printable_glyph_list([key]+ligature.Component),
                    ligature.LigGlyph))

    elif lookup_type == 5 and subtable.Format == 1:
        for index in range(subtable.SubRuleSetCount):
            glyph = subtable.Coverage.glyphs[index]
            for subrule in subtable.SubRuleSet[index].SubRule:
                whole_input = [glyph] + subrule.Input
                print_contextual_substitution(
                    [], whole_input, [], subrule.SubstLookupRecord)

    elif lookup_type == 5 and subtable.Format == 2:
        print_indented('type=%d format=%d not supported yet' % (
            lookup_type, subtable.Format))
#        assert (max(subtable.ClassDef.classDefs.values())
#                <= subtable.SubClassSetCount)
#        assert len(subtable.SubClassSet) == subtable.SubClassSetCount
#        print subtable.Coverage.glyphs
#        print subtable.ClassDef.classDefs
#        for index in range(subtable.SubClassSetCount):
#            sub_class = subtable.SubClassSet[index]
#            if sub_class:
#                print index, vars(sub_class)
#            else:
#                print index, sub_class

    elif lookup_type == 5 and subtable.Format == 3:
        print_contextual_substitution(
            [], subtable.Coverage, [], subtable.SubstLookupRecord)

    elif lookup_type in [6, 8]:
        is_reverse = (lookup_type == 8)
        if subtable.Format == 1:
            print_contextual_substitution(
                subtable.BacktrackCoverage,
                [subtable.Coverage],
                subtable.LookAheadCoverage,
                subtable.Substitute,
                reverse=is_reverse)
        elif subtable.Format == 3:
            print_contextual_substitution(
                subtable.BacktrackCoverage,
                subtable.InputCoverage,
                subtable.LookAheadCoverage,
                subtable.SubstLookupRecord,
                reverse=is_reverse)
        else:
            print_indented('# type=%d format=%d not supported yet' % (
                lookup_type, subtable.Format))


    else:
        print_indented('# type=%d format=%d not supported yet' % (
            lookup_type, subtable.Format))
#    print vars(subtable)


def printable_value_record(value_record):
    """Prints a GPOS ValueRecord."""
    if value_record is None:
        return '<NULL>'

    if vars(value_record).keys() == ['XAdvance']:
        return '%d' % value_record.XAdvance

    output_list = []
    for key in ['XPlacement', 'YPlacement', 'XAdvance', 'YAdvance']:
        output_list.append(vars(value_record).get(key, 0))
    return '<%d %d %d %d>' % tuple(output_list)


def printable_device(device):
    """Returns a printable form of a device record."""
    if device is None:
        return '<device NULL>'
      
    output_list = []
    assert device.StartSize + len(device.DeltaValue) - 1 == device.EndSize
    for index in range(len(device.DeltaValue)):
        output_list.append('%d %d' % (
            device.StartSize + index,
            device.DeltaValue[index]))
    return '<device %s>' % (', '.join(output_list))
  

def printable_anchor(anchor):
    """Returns a printable form of an anchor."""
    if anchor is None:
        return '<anchor NULL>'
    if anchor.Format == 1:
        return '<anchor %d %d>' % (anchor.XCoordinate, anchor.YCoordinate)
    elif anchor.Format == 2:
        return '<anchor %d %d contourpoint %d>' % (
            anchor.XCoordinate,
            anchor.YCoordinate,
            anchor.AnchorPoint)
    elif anchor.Format == 3:
        return '<anchor %d %d %s %s>' % (
            anchor.XCoordinate,
            anchor.YCoordinate,
            printable_device(anchor.XDeviceTable),
            printable_device(anchor.YDeviceTable))
    else:
        print vars(anchor)
        assert False, "don't know about anchor format"


def dump_marks(glyphs, records):
    """Prints marks with their classes."""
    index = 0
    for glyph in glyphs:
        record = records[index]
        print_indented(
            '%s: class=%d %s' % (
                glyph, record.Class, printable_anchor(record.MarkAnchor)),
            indents=2)
        index += 1


def dump_bases(glyphs, records, printable_function):
    """Prints bases with their classes."""
    index = 0
    for glyph in glyphs:
        record = records[index]
        print_indented(
            '%s: %s' % (glyph, printable_function(record)),
            indents=2)
        index += 1


def reverse_class_def(class_def_dict):
    """Reverses a ClassDef dictionary."""
    reverse = {}
    for key in class_def_dict:
        value = class_def_dict[key]
        try:
            reverse[value].add(key)
        except KeyError:
            reverse[value] = {key}
    return reverse
    

def dump_gpos_subtable(lookup_type, subtable):
    """Prints a GPOS subtable."""
    if lookup_type == 9:
        # Extension. Decompile and pass down as another lookup type
        lookup_type = subtable.ExtensionLookupType
        print_indented('# (extension for %d)' % lookup_type)
        ext_sub_table = subtable.ExtSubTable
        subtable = ext_sub_table

    if lookup_type == 1 and subtable.Format == 1:
        print_indented('position %s %s;' % (
            printable_glyph_class(subtable.Coverage.glyphs),
            printable_value_record(subtable.Value)))
    
    elif lookup_type == 1 and subtable.Format == 2:
        for index, value_record in enumerate(subtable.Value):
            print_indented('position %s %s;' % (
                subtable.Coverage.glyphs[index],
                printable_value_record(value_record)))
    
    elif lookup_type == 2 and subtable.Format == 1:
        first_glyphs = subtable.Coverage.glyphs
        for index, pair_set in enumerate(subtable.PairSet):
            first_glyph = first_glyphs[index]
            for pair_value_record in pair_set.PairValueRecord:
                if pair_value_record.Value2 is None:
                    print_indented(
                        'position %s %s %s;' % (
                        first_glyph,
                        pair_value_record.SecondGlyph,
                        printable_value_record(pair_value_record.Value1)))
                else:
                    print_indented(
                        'position %s %s %s %s;' % (
                        first_glyph,
                        printable_value_record(pair_value_record.Value1),
                        pair_value_record.SecondGlyph,
                        printable_value_record(pair_value_record.Value2)))

    elif lookup_type == 2 and subtable.Format == 2:
        class1_reverse = reverse_class_def(subtable.ClassDef1.classDefs)
        class2_reverse = reverse_class_def(subtable.ClassDef2.classDefs)
        for index1, class1_record in enumerate(subtable.Class1Record):
            class1 = class1_reverse.get(index1)
            if class1 is None:
                continue
            for index2, class2_record in enumerate(class1_record.Class2Record):
                class2 = class2_reverse.get(index2)
                if class2 is None:
                    continue
                if class2_record.Value2 is None:
                    value_record1 = printable_value_record(class2_record.Value1)
                    if value_record1 == '0':
                        continue
                    print_indented(
                        'position %s %s %s;' % (
                        printable_glyph_class(class1),
                        printable_glyph_class(class2),
                        value_record1))
                else:
                    print_indented(
                        'position %s %s %s %s;' % (
                        printable_glyph_class(class1),
                        printable_value_record(class2_record.Value1),
                        printable_glyph_class(class2),
                        printable_value_record(class2_record.Value2)))

    elif lookup_type == 3 and subtable.Format == 1:
        for index, entry_exit_record in enumerate(subtable.EntryExitRecord):
            print_indented(
                'position cursive %s %s %s;' % (
                subtable.Coverage.glyphs[index],
                printable_anchor(entry_exit_record.EntryAnchor),
                printable_anchor(entry_exit_record.ExitAnchor)))

    elif lookup_type == 4:
        print_indented('Mark:')
        dump_marks(subtable.MarkCoverage.glyphs, subtable.MarkArray.MarkRecord)

        print_indented('Base:')
        dump_bases(
            subtable.BaseCoverage.glyphs,
            subtable.BaseArray.BaseRecord,
            lambda record: ' '.join([printable_anchor(anchor)
                                    for anchor in record.BaseAnchor]))

    elif lookup_type == 5:
        print_indented('Mark:')
        dump_marks(subtable.MarkCoverage.glyphs, subtable.MarkArray.MarkRecord)
        
        def printable_ligature_attach(attach):
            """Output routine for LigatureAttach."""
            output_list = []
            for record in attach.ComponentRecord:
                anchor_list = []
                for anchor in record.LigatureAnchor:
                    anchor_list.append(printable_anchor(anchor))
                output_list.append(' '.join(anchor_list))
            return ', '.join(output_list)
          
        print_indented('Liga:')
        dump_bases(
            subtable.LigatureCoverage.glyphs,
            subtable.LigatureArray.LigatureAttach,
            printable_ligature_attach)
   
    elif lookup_type == 6:
        print_indented('Mark1:')
        dump_marks(subtable.Mark1Coverage.glyphs,
                   subtable.Mark1Array.MarkRecord)

        print_indented('Mark2:')
        dump_bases(
            subtable.Mark2Coverage.glyphs,
            subtable.Mark2Array.Mark2Record,
            lambda record: ' '.join([printable_anchor(anchor)
                                    for anchor in record.Mark2Anchor]))

    elif lookup_type == 8 and subtable.Format == 3:
        print_contextual_substitution(
            subtable.BacktrackCoverage,
            subtable.InputCoverage,
            subtable.LookAheadCoverage,
            subtable.PosLookupRecord)
    else:
        print_indented('type=%d format=%d not supported yet' % (
            lookup_type, subtable.Format))


def dump_script_record(script_record):
    """Prints out scripts records."""
    for script in script_record:
        script_tag = script.ScriptTag
        default_lang_sys = script.Script.DefaultLangSys
        if default_lang_sys:
            dump_lang_sys(script_tag, 'dflt', default_lang_sys)
        for lang_sys_record in script.Script.LangSysRecord:
            dump_lang_sys(script_tag, lang_sys_record.LangSysTag,
                          lang_sys_record.LangSys)


def dump_feature_record(feature_record):
    """Prints out feature records."""
    for index in range(len(feature_record)):
        record = feature_record[index]
        tag = record.FeatureTag
        feature = record.Feature
        print index, tag, feature.LookupListIndex
        if feature.FeatureParams is not None:
            print_indented('# name <%s>;' % feature.FeatureParams.UINameID)


def dump_lookup_list(lookup_list, table_name):
    """Prints out a lookup list."""
    for index in range(len(lookup_list)):
        lookup = lookup_list[index]
        print 'lookup %d { # type=%d flag=0x%X' % (
            index, lookup.LookupType, lookup.LookupFlag)
    
        for subtable in lookup.SubTable:
            if table_name == 'GSUB':
                dump_gsub_subtable(lookup.LookupType, subtable)
            elif table_name == 'GPOS':
                dump_gpos_subtable(lookup.LookupType, subtable)      
    
        print '}'


def dump_otl_table(font, table_name):
    """Prints out an OpenType Layout table."""
    if table_name not in font:
        print 'no %s table' % table_name
        print
        return
    else:
        print '%s' % table_name
        print '----'

    table = font[table_name].table
    dump_script_record(table.ScriptList.ScriptRecord)
    print
    dump_feature_record(table.FeatureList.FeatureRecord)
    print
    dump_lookup_list(table.LookupList.Lookup, table_name)
    print



def main():
    """Dump the OpenType Layout tables for all input arguments."""
    for font_file_name in sys.argv[1:]:
        font = ttLib.TTFont(font_file_name)
        print '%s: %s' % (font_file_name, internal_font_name(font))
        dump_otl_table(font, 'GPOS')
        dump_otl_table(font, 'GSUB')


if __name__ == '__main__':
    main()
