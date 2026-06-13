"""Split a web font into unicode-range chunks."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fontTools.ttLib import TTFont

from tables.cbdt_cblc import FontMetrics, build_cbdt, build_cblc
from tables.skeleton import add_raw_table

if TYPE_CHECKING:
    from shaping.sequences import SequenceRule

LOG = logging.getLogger(__name__)

_ALWAYS_SHARED: set[int] = (
    {0x200D, 0xFE0F, 0x200C}
    | set(range(0x1F3FB, 0x1F400))
)

DEFAULT_MAX_CHUNK_BYTES = 500 * 1024  # 500 KB target per chunk
_OVERHEAD_ESTIMATE = 80 * 1024


def _analyze_gsub(
    font: TTFont,
) -> tuple[dict[str, set[str]], dict[str, set[str]], list[tuple[str, list[str], str]]]:
    """Read GSUB ligature lookups used by the splitter."""
    comp_map: dict[str, set[str]] = {}
    res_map: dict[str, set[str]] = {}
    lig_rules: list[tuple[str, list[str], str]] = []
    if "GSUB" not in font:
        return comp_map, res_map, lig_rules
    gsub = font["GSUB"].table
    if not gsub.LookupList:
        return comp_map, res_map, lig_rules
    for lookup in gsub.LookupList.Lookup:
        if lookup.LookupType != 4:  # LigatureSubst
            continue
        for st in lookup.SubTable:
            ligs = getattr(st, "ligatures", None)
            if not ligs:
                continue
            for first, lig_list in ligs.items():
                cs = comp_map.setdefault(first, set())
                rs = res_map.setdefault(first, set())
                cs.add(first)
                for lig in lig_list:
                    cs.update(lig.Component)
                    rs.add(lig.LigGlyph)
                    lig_rules.append((first, list(lig.Component), lig.LigGlyph))
    return comp_map, res_map, lig_rules


def _rules_from_sequence_rules(
    cmap: dict[int, str],
    rules: tuple["SequenceRule", ...] | list["SequenceRule"],
) -> tuple[dict[str, set[str]], dict[str, set[str]], list[tuple[str, list[str], str]]]:
    comp_map: dict[str, set[str]] = {}
    res_map: dict[str, set[str]] = {}
    lig_rules: list[tuple[str, list[str], str]] = []
    for rule in rules:
        names = [cmap.get(cp) for cp in rule.components]
        if len(names) < 2 or any(name is None for name in names):
            continue
        first = names[0]
        assert first is not None
        components = [name for name in names[1:] if name is not None]
        comp_map.setdefault(first, set()).update([first, *components])
        res_map.setdefault(first, set()).add(rule.replacement)
        lig_rules.append((first, components, rule.replacement))
    return comp_map, res_map, lig_rules


def _reverse_cmap(cmap: dict[int, str]) -> dict[str, set[int]]:
    rev: dict[str, set[int]] = {}
    for cp, name in cmap.items():
        rev.setdefault(name, set()).add(cp)
    return rev


def _unicodes_to_range_string(cps: set[int]) -> str:
    """Format codepoints as a CSS unicode-range value (contiguous runs collapsed)."""
    if not cps:
        return ""
    s = sorted(cps)
    parts: list[str] = []
    lo = hi = s[0]
    for cp in s[1:]:
        if cp == hi + 1:
            hi = cp
        else:
            parts.append(f"U+{lo:04X}" if lo == hi else f"U+{lo:04X}-{hi:04X}")
            lo = hi = cp
    parts.append(f"U+{lo:04X}" if lo == hi else f"U+{lo:04X}-{hi:04X}")
    return ", ".join(parts)


def _active_for_codepoint(
    cp: int,
    cmap: dict[int, str],
    comp_map: dict[str, set[str]],
    res_map: dict[str, set[str]],
) -> set[str]:
    active: set[str] = set()
    gname = cmap.get(cp)
    if not gname:
        return active
    active.add(gname)
    if gname in comp_map:
        active |= comp_map[gname]
    if gname in res_map:
        active |= res_map[gname]
    return active


def split_web_font(
    font_bytes: bytes,
    glyphs: list[tuple[int, str, bytes]],
    output_path: Path,
    ppem: int,
    font_metrics: FontMetrics,
    *,
    y_bearing: str = "five_sixths_height",
    max_chunk_bytes: int = DEFAULT_MAX_CHUNK_BYTES,
    sequence_rules: tuple["SequenceRule", ...] | list["SequenceRule"] = (),
) -> list[tuple[str, Path]]:
    """Split a font into budget-sized chunks for @font-face delivery."""
    font = TTFont(io.BytesIO(font_bytes))
    cmap = font.getBestCmap() or {}
    rev = _reverse_cmap(cmap)
    if sequence_rules:
        comp_map, res_map, lig_rules = _rules_from_sequence_rules(cmap, sequence_rules)
    else:
        comp_map, res_map, lig_rules = _analyze_gsub(font)
    font.close()

    base_cps = sorted(cp for cp in cmap if cp not in _ALWAYS_SHARED)
    if not base_cps:
        return []

    glyph_sizes: dict[str, int] = {name: len(png) for _gid, name, png in glyphs}
    avg_size = sum(glyph_sizes.values()) / max(len(glyph_sizes), 1)

    shared_active: set[str] = set()
    for cp in _ALWAYS_SHARED:
        gname = cmap.get(cp)
        if not gname:
            continue
        shared_active.add(gname)
        if gname in comp_map:
            shared_active |= comp_map[gname]
        if gname in res_map:
            shared_active |= res_map[gname]

    def _estimate_bytes(names: set[str]) -> int:
        return sum(glyph_sizes.get(n, int(avg_size)) for n in names)

    shared_cost = _estimate_bytes(shared_active)
    bitmap_budget = max_chunk_bytes - _OVERHEAD_ESTIMATE

    chunks: list[list[int]] = []
    cur_chunk: list[int] = []
    cur_active: set[str] = set(shared_active)
    cur_cost = shared_cost

    for cp in base_cps:
        cp_active = _active_for_codepoint(cp, cmap, comp_map, res_map)
        new_names = cp_active - cur_active
        new_cost = _estimate_bytes(new_names)

        if cur_chunk and (cur_cost + new_cost) > bitmap_budget:
            chunks.append(cur_chunk)
            cur_chunk = []
            cur_active = set(shared_active)
            cur_cost = shared_cost
            new_names = cp_active - cur_active
            new_cost = _estimate_bytes(new_names)

        cur_chunk.append(cp)
        cur_active |= cp_active
        cur_cost += new_cost

    if cur_chunk:
        chunks.append(cur_chunk)

    LOG.info(
        "Splitting %d base codepoints into %d chunks (budget %d KB)",
        len(base_cps), len(chunks), max_chunk_bytes // 1024,
    )

    out: list[tuple[str, Path]] = []
    for idx, cp_list in enumerate(chunks):
        range_cps: set[int] = set(cp_list) | _ALWAYS_SHARED

        for cp in cp_list:
            gname = cmap.get(cp)
            if gname and gname in comp_map:
                for comp_name in comp_map[gname]:
                    comp_cps = rev.get(comp_name)
                    if comp_cps:
                        range_cps |= comp_cps

        active: set[str] = set()

        range_glyph_names: set[str] = set()
        for cp in range_cps:
            name = cmap.get(cp)
            if name:
                active.add(name)
                range_glyph_names.add(name)

        for cp in set(cp_list) | _ALWAYS_SHARED:
            gname = cmap.get(cp)
            if not gname:
                continue
            if gname in comp_map:
                active |= comp_map[gname]

        n_results = 0
        for first, components, result in lig_rules:
            all_names = [first] + components
            all_in_range = True
            for comp_name in all_names:
                if comp_name not in range_glyph_names:
                    all_in_range = False
                    break
            if all_in_range:
                active.add(result)
                n_results += 1

        chunk_glyphs = [
            (gid, name, png) for gid, name, png in glyphs if name in active
        ]
        if not chunk_glyphs:
            continue

        cbdt, locs = build_cbdt(chunk_glyphs, ppem, font_metrics, y_bearing=y_bearing)
        cblc = build_cblc(cbdt, chunk_glyphs, locs, ppem, font_metrics)

        cfont = TTFont(io.BytesIO(font_bytes))
        add_raw_table(cfont, "CBDT", cbdt)
        add_raw_table(cfont, "CBLC", cblc)
        if "post" in cfont:
            cfont["post"].formatType = 3.0
            cfont["post"].extraNames = []
            cfont["post"].mapping = {}

        p = output_path.parent / f"{output_path.stem}[{idx + 1}]{output_path.suffix}"
        cfont.save(p)
        cfont.close()

        rstr = _unicodes_to_range_string(range_cps)
        out.append((rstr, p))

        LOG.info(
            "Chunk %d: %d primary + %d results = %d bitmap glyphs -> %s",
            idx + 1, len(cp_list), n_results, len(chunk_glyphs), p.name,
        )

    return out


def write_css(
    path: Path,
    chunks: list[tuple[str, Path]],
    font_family: str = "Apple Color Emoji",
) -> None:
    """Write @font-face CSS with unicode-range per chunk."""
    lines = [
        f"/* {len(chunks)} emoji font chunks - font-family: '{font_family}' */",
        "",
    ]
    for rstr, fp in chunks:
        lines += [
            "@font-face {",
            f"  font-family: '{font_family}';",
            "  font-display: swap;",
            f"  src: url('{fp.name}') format('truetype');",
            f"  unicode-range: {rstr};",
            "}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
