#!/usr/bin/env python3
"""Build GSUB ligatures from cached HarfBuzz shaping results."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.G_S_U_B_ import table_G_S_U_B_
from fontTools.otlLib.builder import buildLookup

LOG = logging.getLogger(__name__)


def _codepoint_from_glyph_name(name: str) -> int | None:
    if name == "ZWJ":
        return 0x200D
    if name == "VS16":
        return 0xFE0F

    base = name.split(".", 1)[0]
    if base.startswith("uni"):
        hex_part = base[3:]
    elif base.startswith("u"):
        hex_part = base[1:]
    else:
        return None
    if not hex_part or not all(c in "0123456789ABCDEFabcdef" for c in hex_part):
        return None
    try:
        return int(hex_part, 16)
    except ValueError:
        return None


def _resolve_component(font: TTFont, name: str, *, prefer_cmap: bool = False) -> str | None:
    glyph_order = font.getGlyphOrder()
    if prefer_cmap:
        codepoint = _codepoint_from_glyph_name(name)
        cmap = font.getBestCmap() if codepoint is not None else None
        resolved = cmap.get(codepoint) if cmap else None
        if resolved in glyph_order:
            return resolved
    if name in glyph_order:
        return name
    codepoint = _codepoint_from_glyph_name(name)
    if codepoint is not None:
        cmap = font.getBestCmap()
        resolved = cmap.get(codepoint) if cmap else None
        if resolved in glyph_order:
            return resolved
    if "." in name:
        base = name.split(".", 1)[0]
        if base in glyph_order:
            return base
    return None


def _load_ligatures(cache_path: Path) -> list[tuple[list[str], str]]:
    """Load [[components], replacement] from JSON cache."""
    with open(cache_path, encoding="utf-8") as f:
        raw = json.load(f)
    out: list[tuple[list[str], str]] = []
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        comps, repl = entry[0], entry[1]
        if not comps or not isinstance(repl, str):
            continue
        out.append((list(comps), repl))
    return out


def _build_ligature_subtable(
    font: TTFont,
    ligatures: list[tuple[list[str], str]],
) -> ot.LigatureSubst | None:
    """Build a LigatureSubst subtable."""
    resolved: list[tuple[list[str], str]] = []
    skipped_repl = 0
    skipped_comp = 0
    for comps, repl in ligatures:
        resolved_repl = _resolve_component(font, repl)
        if resolved_repl is None:
            skipped_repl += 1
            continue
        resolved_comps = []
        for c in comps:
            r = _resolve_component(font, c, prefer_cmap=True)
            if r is None:
                break
            resolved_comps.append(r)
        if len(resolved_comps) == len(comps):
            resolved.append((resolved_comps, resolved_repl))
        else:
            skipped_comp += 1

    LOG.info(
        "Ligature resolution: %d resolved, %d skipped (replacement not found), %d skipped (component not found)",
        len(resolved), skipped_repl, skipped_comp,
    )

    if not resolved:
        return None

    from itertools import combinations
    cmap = font.getBestCmap()
    vs16_name = cmap.get(0xFE0F) if cmap else None
    if vs16_name:
        vs16_variants: list[tuple[list[str], str]] = []
        for comps, repl in resolved:
            positions = [i for i, c in enumerate(comps) if c == vs16_name]
            if not positions:
                continue
            for r in range(1, len(positions) + 1):
                for to_remove in combinations(positions, r):
                    remove_set = set(to_remove)
                    variant = [c for i, c in enumerate(comps) if i not in remove_set]
                    if len(variant) >= 2:
                        vs16_variants.append((variant, repl))
        if vs16_variants:
            resolved.extend(vs16_variants)
            LOG.info("Added %d VS16-variant ligatures (partial + full strip)", len(vs16_variants))

    seen: set[tuple[str, ...]] = set()
    deduped: list[tuple[list[str], str]] = []
    for comps, repl in resolved:
        key = tuple(comps)
        if key not in seen:
            seen.add(key)
            deduped.append((comps, repl))
    if len(deduped) < len(resolved):
        LOG.info("Deduplicated: %d -> %d ligatures", len(resolved), len(deduped))
    resolved = deduped

    by_first: dict[str, list[tuple[list[str], str]]] = {}
    for comps, repl in resolved:
        first = comps[0]
        by_first.setdefault(first, []).append((comps, repl))
    for first in by_first:
        by_first[first].sort(key=lambda x: -len(x[0]))

    st = ot.LigatureSubst()
    st.ligatures = {}
    for first, group in by_first.items():
        lig_list = []
        for comps, repl in group:
            lig = ot.Ligature()
            lig.LigGlyph = repl
            lig.CompCount = len(comps)
            lig.Component = comps[1:]
            lig_list.append(lig)
        st.ligatures[first] = lig_list
    return st


def _build_vs16_deletion_lookup(font: TTFont) -> ot.Lookup | None:
    cmap = font.getBestCmap()
    vs16_name = cmap.get(0xFE0F)
    if vs16_name is None:
        return None

    glyph_order = font.getGlyphOrder()
    if vs16_name not in glyph_order:
        return None

    st = ot.MultipleSubst()
    st.mapping = {vs16_name: []}

    return buildLookup([st], flags=0, markFilterSet=None)


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


def _build_gsub_table(
    ligature_lookup: ot.Lookup,
    vs16_lookup: ot.Lookup | None = None,
) -> ot.GSUB:
    lookups: list[ot.Lookup] = []
    ccmp_indices: list[int] = []

    if vs16_lookup is not None:
        ccmp_indices.append(len(lookups))
        lookups.append(vs16_lookup)

    ccmp_indices.append(len(lookups))
    lookups.append(ligature_lookup)

    num_features = 1
    feature_indices = list(range(num_features))

    gsub = ot.GSUB()
    gsub.Version = 0x00010000
    gsub.ScriptList = ot.ScriptList()
    gsub.ScriptList.ScriptRecord = [
        _build_script_record("DFLT", feature_indices),
        _build_script_record("latn", feature_indices),
    ]
    gsub.ScriptList.ScriptCount = len(gsub.ScriptList.ScriptRecord)

    gsub.FeatureList = ot.FeatureList()
    gsub.FeatureList.FeatureCount = num_features

    feat_ccmp = ot.FeatureRecord()
    feat_ccmp.FeatureTag = "ccmp"
    feat_ccmp.Feature = ot.Feature()
    feat_ccmp.Feature.FeatureParams = None
    feat_ccmp.Feature.LookupListIndex = ccmp_indices
    feat_ccmp.Feature.LookupCount = len(ccmp_indices)

    gsub.FeatureList.FeatureRecord = [feat_ccmp]

    gsub.LookupList = ot.LookupList()
    gsub.LookupList.LookupCount = len(lookups)
    gsub.LookupList.Lookup = lookups
    gsub.FeatureVariations = None
    return gsub


def build_gsub_from_morx(
    font: TTFont,
    *,
    font_path: Path | None = None,
    font_number: int = 0,
    ligatures_cache_path: Path | None = None,
    recompute_ligatures: bool = False,
    delete_vs16: bool = True,
    extra_ligatures: list[tuple[list[str], str]] | None = None,
):
    """Build a fontTools GSUB table wrapper."""
    cache_path = ligatures_cache_path or Path(".ligatures.json")

    if recompute_ligatures:
        if font_path is None:
            LOG.error("--recompute-ligatures requires --input font path")
            return None
        from generate_ligatures import generate_flattened_ligatures, save_ligatures_cache
        from generate_ligatures import save_multi_glyph_cache

        LOG.info("Recomputing ligatures via HarfBuzz...")
        raw_ligatures, multi_ligatures = generate_flattened_ligatures(font_path, font_number)
        if not raw_ligatures and not multi_ligatures:
            LOG.error("No ligatures generated")
            return None
        if raw_ligatures:
            save_ligatures_cache(raw_ligatures, cache_path)
        multi_cache = cache_path.parent / ".ligatures-multi.json"
        if multi_ligatures:
            save_multi_glyph_cache(multi_ligatures, multi_cache)
        ligatures = raw_ligatures
    elif cache_path.exists():
        ligatures = _load_ligatures(cache_path)
    else:
        LOG.warning("Ligatures cache not found: %s", cache_path)
        return None

    if extra_ligatures:
        ligatures = list(ligatures) + list(extra_ligatures)
        LOG.info("Added %d extra ligatures (merged glyphs)", len(extra_ligatures))

    if not ligatures:
        LOG.warning("No ligatures in cache")
        return None
    LOG.info("Ligatures: %d total", len(ligatures))

    subtable = _build_ligature_subtable(font, ligatures)
    if subtable is None:
        LOG.warning("No ligatures could be resolved to font glyphs")
        return None

    lig_lookup = buildLookup([subtable], flags=0, markFilterSet=None)
    if lig_lookup is None:
        return None

    vs16_lookup = _build_vs16_deletion_lookup(font) if delete_vs16 else None
    if vs16_lookup:
        LOG.info("Added VS16 deletion lookup (ccmp)")

    gsub_table = _build_gsub_table(lig_lookup, vs16_lookup=vs16_lookup)
    wrapper = table_G_S_U_B_()
    wrapper.table = gsub_table
    n_lookups = 2 if vs16_lookup else 1
    LOG.info("Built GSUB: ccmp feature, %d lookup(s)", n_lookups)
    return wrapper
