"""Build GSUB ligatures from sequence rules."""

from __future__ import annotations

import logging

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.G_S_U_B_ import table_G_S_U_B_
from fontTools.otlLib.builder import buildLookup

from shaping.sequences import SequenceRule

LOG = logging.getLogger(__name__)


def build_gsub_from_sequence_rules(
    font: TTFont,
    rules: tuple[SequenceRule, ...] | list[SequenceRule],
) -> table_G_S_U_B_ | None:
    """Build a fontTools GSUB table wrapper from normalized sequence rules."""
    subtable = _build_ligature_subtable(font, rules)
    if subtable is None:
        LOG.warning("No sequence GSUB rules could be resolved")
        return None

    lookup = buildLookup([subtable], flags=0, markFilterSet=None)
    gsub_table = table_G_S_U_B_()
    gsub_table.table = _build_gsub_table(lookup)
    LOG.info("Built sequence GSUB with %d rule(s)", len(rules))
    return gsub_table


def _build_ligature_subtable(
    font: TTFont,
    rules: tuple[SequenceRule, ...] | list[SequenceRule],
) -> ot.LigatureSubst | None:
    cmap = font.getBestCmap() or {}
    glyph_order = set(font.getGlyphOrder())

    resolved: list[tuple[tuple[str, ...], str, tuple[int, ...]]] = []
    skipped_components = 0
    skipped_replacements = 0
    for rule in rules:
        replacement = rule.replacement
        if replacement not in glyph_order:
            skipped_replacements += 1
            continue
        components: list[str] = []
        for codepoint in rule.components:
            glyph_name = cmap.get(codepoint)
            if glyph_name is None or glyph_name not in glyph_order:
                break
            components.append(glyph_name)
        if len(components) != len(rule.components) or len(components) < 2:
            skipped_components += 1
            continue
        resolved.append((tuple(components), replacement, rule.components))

    if skipped_components or skipped_replacements:
        LOG.info(
            "Sequence GSUB resolution: %d resolved, %d skipped components, %d skipped replacements",
            len(resolved),
            skipped_components,
            skipped_replacements,
        )
    if not resolved:
        return None

    deduped: dict[tuple[str, ...], tuple[str, tuple[int, ...]]] = {}
    for components, replacement, codepoints in resolved:
        deduped.setdefault(components, (replacement, codepoints))

    by_first: dict[str, list[tuple[tuple[str, ...], str, tuple[int, ...]]]] = {}
    for components, (replacement, codepoints) in deduped.items():
        by_first.setdefault(components[0], []).append((components, replacement, codepoints))

    subtable = ot.LigatureSubst()
    subtable.ligatures = {}
    for first, group in by_first.items():
        group.sort(key=lambda item: (-len(item[0]), item[2]))
        ligatures: list[ot.Ligature] = []
        for components, replacement, _codepoints in group:
            ligature = ot.Ligature()
            ligature.LigGlyph = replacement
            ligature.CompCount = len(components)
            ligature.Component = list(components[1:])
            ligatures.append(ligature)
        subtable.ligatures[first] = ligatures
    return subtable


def _build_script_record(tag: str, feature_indices: list[int]) -> ot.ScriptRecord:
    rec = ot.ScriptRecord()
    rec.ScriptTag = tag
    rec.Script = ot.Script()
    rec.Script.DefaultLangSys = ot.DefaultLangSys()
    rec.Script.DefaultLangSys.ReqFeatureIndex = 0xFFFF
    rec.Script.DefaultLangSys.FeatureIndexCount = len(feature_indices)
    rec.Script.DefaultLangSys.FeatureIndex = feature_indices
    rec.Script.LangSysRecord = []
    rec.Script.LangSysCount = 0
    return rec


def _build_gsub_table(ligature_lookup: ot.Lookup) -> ot.GSUB:
    gsub = ot.GSUB()
    gsub.Version = 0x00010000

    gsub.ScriptList = ot.ScriptList()
    gsub.ScriptList.ScriptRecord = [
        _build_script_record("DFLT", [0]),
        _build_script_record("latn", [0]),
    ]
    gsub.ScriptList.ScriptCount = len(gsub.ScriptList.ScriptRecord)

    gsub.FeatureList = ot.FeatureList()
    feature = ot.FeatureRecord()
    feature.FeatureTag = "ccmp"
    feature.Feature = ot.Feature()
    feature.Feature.LookupListIndex = [0]
    feature.Feature.LookupCount = 1
    gsub.FeatureList.FeatureRecord = [feature]
    gsub.FeatureList.FeatureCount = 1

    gsub.LookupList = ot.LookupList()
    gsub.LookupList.Lookup = [ligature_lookup]
    gsub.LookupList.LookupCount = 1
    return gsub
