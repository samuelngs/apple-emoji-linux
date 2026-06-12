#!/usr/bin/env python3
"""Generate GSUB ligature caches from HarfBuzz shaping results."""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

LOG = logging.getLogger(__name__)

ZWJ = 0x200D
VS16 = 0xFE0F

FITZPATRICK = [0x1F3FB, 0x1F3FC, 0x1F3FD, 0x1F3FE, 0x1F3FF]
FITZPATRICK_SET = frozenset(FITZPATRICK)

# Gender signs
FEMALE = 0x2640
MALE = 0x2642

# Direction arrow
RIGHT_ARROW = 0x27A1

# Adults / children for family sequences
ADULTS = [0x1F468, 0x1F469]       # man, woman
ADULT_NEUTRAL = 0x1F9D1           # adult (gender-neutral)
CHILDREN = [0x1F466, 0x1F467]     # boy, girl
CHILD_NEUTRAL = 0x1F9D2           # child (gender-neutral)

# Couple components
HANDSHAKE = 0x1F91D
HEART = 0x2764
KISS_MARK = 0x1F48B

# Base emojis that have gendered ZWJ variants (base + ZWJ + gender sign)
GENDERED_BASES = [
    0x1F468,  # man
    0x1F469,  # woman
    0x1F9D1,  # person
    0x1F46E,  # police officer
    0x1F473,  # person with turban
    0x1F477,  # construction worker
    0x1F482,  # guard
    0x1F575,  # detective
    0x1F647,  # person bowing
    0x1F64B,  # person raising hand
    0x1F64D,  # person frowning
    0x1F64E,  # person pouting
    0x1F6A3,  # person rowing boat
    0x1F926,  # person facepalming
    0x1F937,  # person shrugging
    0x1F9D6,  # person in steamy room
    0x1F9D7,  # person climbing
    0x1F9D8,  # person in lotus position
    0x1F9D9,  # mage
    0x1F9DA,  # fairy
    0x1F9DB,  # vampire
    0x1F9DC,  # merperson
    0x1F9DD,  # elf
    0x1F9DE,  # genie
    0x1F9DF,  # zombie
    0x26F9,   # person bouncing ball
    0x1F3C3,  # person running
    0x1F3C4,  # person surfing
    0x1F3CA,  # person swimming
    0x1F3CB,  # person lifting weights
    0x1F3CC,  # person golfing
    0x1F6B4,  # person biking
    0x1F6B5,  # person mountain biking
    0x1F6B6,  # person walking
    0x1F9CE,  # person kneeling
    0x1F9CF,  # deaf person
    0x1F9D4,  # person with beard
]

# Profession/object ZWJ combos: person + ZWJ + object
PROFESSION_OBJECTS = [
    0x2695,   # medical (staff of Aesculapius)
    0x2696,   # judge (scales)
    0x2708,   # pilot (airplane)
    0x1F33E,  # farmer (rice)
    0x1F373,  # cook (egg)
    0x1F393,  # student (graduation cap)
    0x1F3A4,  # singer (microphone)
    0x1F3A8,  # artist (palette)
    0x1F3EB,  # teacher (school)
    0x1F3ED,  # factory worker
    0x1F4BB,  # technologist (laptop)
    0x1F4BC,  # office worker (briefcase)
    0x1F527,  # mechanic (wrench)
    0x1F52C,  # scientist (microscope)
    0x1F680,  # astronaut (rocket)
    0x1F37C,  # baby bottle (feeding)
    0x1F692,  # firefighter (fire engine)
    0x1F9AF,  # person with white cane
    0x1F9B0,  # red hair
    0x1F9B1,  # curly hair
    0x1F9B2,  # bald
    0x1F9B3,  # white hair
    0x1F9BC,  # person in motorized wheelchair
    0x1F9BD,  # person in manual wheelchair
]

# Emojis that have directional variants (base + ZWJ + arrow)
DIRECTIONAL_BASES = [
    0x1F3C3,  # person running
    0x1F6B6,  # person walking
    0x1F9CE,  # person kneeling
    0x1F9D1,  # person
    0x1F468,  # man
    0x1F469,  # woman
]

# Directional emojis with accessory (person + ZWJ + accessory + ZWJ + arrow)
DIRECTIONAL_WITH_ACCESSORY = [
    0x1F9AF,  # white cane
    0x1F9BC,  # motorized wheelchair
    0x1F9BD,  # manual wheelchair
]

# Flag tag sequences: black flag + tag chars + cancel tag
FLAG_TAGS = {
    "gbeng": [0x1F3F4, 0xE0067, 0xE0062, 0xE0065, 0xE006E, 0xE0067, 0xE007F],  # England
    "gbsct": [0x1F3F4, 0xE0067, 0xE0062, 0xE0073, 0xE0063, 0xE0074, 0xE007F],  # Scotland
    "gbwls": [0x1F3F4, 0xE0067, 0xE0062, 0xE0077, 0xE006C, 0xE0073, 0xE007F],  # Wales
}

def _with_skin_tones(base_seq: list[int]) -> list[list[int]]:
    out = [list(base_seq)]
    for tone in FITZPATRICK:
        seq = [base_seq[0], tone] + list(base_seq[1:])
        out.append(seq)
    return out


def enumerate_zwj_sequences() -> list[list[int]]:
    """Enumerate all emoji ZWJ codepoint sequences to test."""
    sequences: list[list[int]] = []

    for person in [0x1F468, 0x1F469, 0x1F9D1]:
        for obj in PROFESSION_OBJECTS:
            base = [person, ZWJ, obj]
            sequences.extend(_with_skin_tones(base))

    for base_cp in GENDERED_BASES:
        for gender in [FEMALE, MALE]:
            base = [base_cp, ZWJ, gender]
            sequences.extend(_with_skin_tones(base))
            base_vs = [base_cp, ZWJ, gender, VS16]
            sequences.extend(_with_skin_tones(base_vs))

    for base_cp in DIRECTIONAL_BASES:
        for seq in _with_skin_tones([base_cp, ZWJ, RIGHT_ARROW, VS16]):
            sequences.append(seq)
        for gender in [FEMALE, MALE]:
            for seq in _with_skin_tones([base_cp, ZWJ, gender, VS16, ZWJ, RIGHT_ARROW, VS16]):
                sequences.append(seq)
            for seq in _with_skin_tones([base_cp, ZWJ, gender, ZWJ, RIGHT_ARROW, VS16]):
                sequences.append(seq)

    for person in [0x1F468, 0x1F469, 0x1F9D1]:
        for acc in DIRECTIONAL_WITH_ACCESSORY:
            base = [person, ZWJ, acc, ZWJ, RIGHT_ARROW, VS16]
            sequences.extend(_with_skin_tones(base))

    all_people = ADULTS + [ADULT_NEUTRAL]
    all_children = CHILDREN + [CHILD_NEUTRAL]

    for a1, a2 in itertools.product(all_people, repeat=2):
        sequences.append([a1, ZWJ, a2])

    for a1, a2 in itertools.product(all_people, repeat=2):
        for c1 in all_children:
            sequences.append([a1, ZWJ, a2, ZWJ, c1])

    for a1, a2 in itertools.product(all_people, repeat=2):
        for c1, c2 in itertools.product(all_children, repeat=2):
            sequences.append([a1, ZWJ, a2, ZWJ, c1, ZWJ, c2])

    for a in all_people:
        for c in all_children:
            sequences.append([a, ZWJ, c])
        for c1, c2 in itertools.product(all_children, repeat=2):
            sequences.append([a, ZWJ, c1, ZWJ, c2])

    for p1, p2 in itertools.product(ADULTS + [ADULT_NEUTRAL], repeat=2):
        base = [p1, ZWJ, HANDSHAKE, ZWJ, p2]
        sequences.append(base)
        for t1 in FITZPATRICK:
            for t2 in FITZPATRICK:
                sequences.append([p1, t1, ZWJ, HANDSHAKE, ZWJ, p2, t2])

    for p1, p2 in itertools.product(ADULTS + [ADULT_NEUTRAL], repeat=2):
        sequences.append([p1, ZWJ, HEART, VS16, ZWJ, p2])
        for t1 in FITZPATRICK:
            for t2 in FITZPATRICK:
                sequences.append([p1, t1, ZWJ, HEART, VS16, ZWJ, p2, t2])

    for p1, p2 in itertools.product(ADULTS + [ADULT_NEUTRAL], repeat=2):
        sequences.append([p1, ZWJ, HEART, VS16, ZWJ, KISS_MARK, ZWJ, p2])
        for t1 in FITZPATRICK:
            for t2 in FITZPATRICK:
                sequences.append([p1, t1, ZWJ, HEART, VS16, ZWJ, KISS_MARK, ZWJ, p2, t2])

    for _name, seq in FLAG_TAGS.items():
        sequences.append(seq)

    KEYCAP_ENCLOSING = 0x20E3
    for base in [0x0023, 0x002A] + list(range(0x0030, 0x003A)):  # #, *, 0-9
        sequences.append([base, VS16, KEYCAP_ENCLOSING])
        sequences.append([base, KEYCAP_ENCLOSING])  # without VS16

    seen: set[tuple[int, ...]] = set()
    unique: list[list[int]] = []
    for seq in sequences:
        key = tuple(seq)
        if key not in seen:
            seen.add(key)
            unique.append(seq)

    return unique


def _shape_once(hb_font, hb_module, seq: list[int], notdef_gids: set[int]) -> list[int]:
    """Shape a codepoint sequence and return meaningful output GIDs."""
    text = "".join(chr(cp) for cp in seq)
    buf = hb_module.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb_module.shape(hb_font, buf)
    return [i.codepoint for i in buf.glyph_infos if i.codepoint not in notdef_gids]


def _resolve_components(
    seq: list[int],
    cmap: dict[int, str],
    glyph_set: set[str],
) -> list[str] | None:
    """Map codepoints to glyph names."""
    comps: list[str] = []
    for cp in seq:
        glyph_name = cmap.get(cp)
        if glyph_name is None:
            for prefix in [f"u{cp:05X}", f"u{cp:04X}", f"uni{cp:04X}"]:
                if prefix in glyph_set:
                    glyph_name = prefix
                    break
            if glyph_name is None:
                return None
        comps.append(glyph_name)
    return comps if len(comps) >= 2 else None


def generate_flattened_ligatures(
    font_path: Path,
    font_number: int = 0,
) -> tuple[list[tuple[list[str], str]], list[tuple[list[str], list[str]]]]:
    """Shape known emoji sequences and return single- and multi-glyph results."""
    try:
        import uharfbuzz as hb
    except ImportError:
        raise ImportError(
            "uharfbuzz is required for --recompute-ligatures. "
            "Install: pip install uharfbuzz"
        ) from None

    ft_font = TTFont(font_path, fontNumber=font_number)
    cmap = ft_font.getBestCmap()
    glyph_order = ft_font.getGlyphOrder()
    glyph_set = set(glyph_order)

    if not cmap:
        LOG.error("Font has no usable cmap")
        return [], []

    notdef_gids: set[int] = set()
    for name in [".notdef", "space", "uni00A0", "CR"]:
        if name in glyph_set:
            notdef_gids.add(glyph_order.index(name))

    with open(font_path, "rb") as f:
        font_data = f.read()
    blob = hb.Blob(font_data)
    face = hb.Face(blob, font_number)
    hb_font = hb.Font(face)

    ligatures: list[tuple[list[str], str]] = []
    multi_ligatures: list[tuple[list[str], list[str]]] = []
    seen_seqs: set[tuple[int, ...]] = set()
    stats = {"single": 0, "multi2": 0, "skipped_multi": 0,
             "skipped_unchanged": 0, "skipped_no_cmap": 0}

    def _process_sequence(seq: list[int]) -> None:
        """Shape one sequence and record the result if useful."""
        key = tuple(seq)
        if key in seen_seqs:
            return
        seen_seqs.add(key)

        output_gids = _shape_once(hb_font, hb, seq, notdef_gids)

        if len(output_gids) == 1:
            result_gid = output_gids[0]
            if result_gid >= len(glyph_order):
                return
            result_name = glyph_order[result_gid]
            comps = _resolve_components(seq, cmap, glyph_set)
            if comps is None:
                stats["skipped_no_cmap"] += 1
                return
            if result_name == comps[0]:
                stats["skipped_unchanged"] += 1
                return
            ligatures.append((comps, result_name))
            stats["single"] += 1

        elif len(output_gids) == 2:
            names = []
            for gid in output_gids:
                if gid >= len(glyph_order):
                    return
                names.append(glyph_order[gid])
            comps = _resolve_components(seq, cmap, glyph_set)
            if comps is None:
                stats["skipped_no_cmap"] += 1
                return
            if names[0] == comps[0] and names[1] == (comps[1] if len(comps) > 1 else comps[0]):
                stats["skipped_unchanged"] += 1
                return
            multi_ligatures.append((comps, names))
            stats["multi2"] += 1

        else:
            stats["skipped_multi"] += 1

    category_sequences = enumerate_zwj_sequences()
    LOG.info("Phase 1: testing %d category-based sequences...", len(category_sequences))
    for seq in category_sequences:
        _process_sequence(seq)
    LOG.info(
        "Phase 1 done: %d single-glyph, %d multi-glyph so far",
        stats["single"], stats["multi2"],
    )

    cmap_cps = sorted(cmap.keys())
    LOG.info(
        "Phase 2: pre-computing solo GIDs for %d cmap entries...",
        len(cmap_cps),
    )

    solo_gid: dict[int, int] = {}
    for cp in cmap_cps:
        gids = _shape_once(hb_font, hb, [cp], notdef_gids)
        if len(gids) == 1:
            solo_gid[cp] = gids[0]

    total_pairs = len(cmap_cps) * len(cmap_cps) * 3
    LOG.info(
        "Phase 2: brute-force %d cmap entries (%d pair variants)...",
        len(cmap_cps), total_pairs,
    )

    phase2_single = 0
    phase2_multi = 0
    phase2_skipped = 0
    phase2_hit_seqs: list[list[int]] = []

    for a in cmap_cps:
        for b in cmap_cps:
            for seq in ([a, b], [a, ZWJ, b], [a, ZWJ, b, VS16]):
                key = tuple(seq)
                if key in seen_seqs:
                    continue
                seen_seqs.add(key)

                output_gids = _shape_once(hb_font, hb, seq, notdef_gids)

                if len(output_gids) == 1:
                    result_gid = output_gids[0]
                    if result_gid == solo_gid.get(b):
                        phase2_skipped += 1
                        continue
                    if result_gid == solo_gid.get(a) and b not in FITZPATRICK_SET:
                        phase2_skipped += 1
                        continue
                    if result_gid >= len(glyph_order):
                        continue
                    result_name = glyph_order[result_gid]
                    comps = _resolve_components(seq, cmap, glyph_set)
                    if comps is None or len(comps) < 2:
                        stats["skipped_no_cmap"] += 1
                        continue
                    ligatures.append((comps, result_name))
                    stats["single"] += 1
                    phase2_single += 1
                    phase2_hit_seqs.append(list(seq))

                elif len(output_gids) == 2:
                    a_solo = solo_gid.get(a)
                    b_solo = solo_gid.get(b)
                    if output_gids[0] == a_solo and output_gids[1] == b_solo:
                        phase2_skipped += 1
                        continue
                    names = []
                    valid = True
                    for gid in output_gids:
                        if gid >= len(glyph_order):
                            valid = False
                            break
                        names.append(glyph_order[gid])
                    if not valid:
                        continue
                    comps = _resolve_components(seq, cmap, glyph_set)
                    if comps is None or len(comps) < 2:
                        stats["skipped_no_cmap"] += 1
                        continue
                    multi_ligatures.append((comps, names))
                    stats["multi2"] += 1
                    phase2_multi += 1

                else:
                    stats["skipped_multi"] += 1

    LOG.info(
        "Phase 2 done: +%d single-glyph, +%d multi-glyph (%d filtered as unchanged)",
        phase2_single, phase2_multi, phase2_skipped,
    )

    phase3_count = 0
    phase3_single = 0
    for base_seq in phase2_hit_seqs:
        first_cp = base_seq[0]
        if first_cp in FITZPATRICK_SET or first_cp in (ZWJ, VS16):
            continue
        for tone in FITZPATRICK:
            variant = [first_cp, tone] + base_seq[1:]
            before = stats["single"]
            _process_sequence(variant)
            if stats["single"] > before:
                phase3_single += 1
            phase3_count += 1

    LOG.info(
        "Phase 3 done: tested %d skin-toned variants, +%d single-glyph",
        phase3_count, phase3_single,
    )

    LOG.info(
        "Final stats: %d single, %d multi-2, skipped: %d multi-3+, %d unchanged, %d no-cmap",
        stats["single"], stats["multi2"],
        stats["skipped_multi"], stats["skipped_unchanged"], stats["skipped_no_cmap"],
    )

    seen_comps: set[tuple[str, ...]] = set()
    deduped: list[tuple[list[str], str]] = []
    for comps, repl in ligatures:
        key = tuple(comps)
        if key not in seen_comps:
            seen_comps.add(key)
            deduped.append((comps, repl))

    seen_multi: set[tuple[str, ...]] = set()
    deduped_multi: list[tuple[list[str], list[str]]] = []
    for comps, repls in multi_ligatures:
        key = tuple(comps)
        if key not in seen_multi:
            seen_multi.add(key)
            deduped_multi.append((comps, repls))

    LOG.info(
        "After dedup: %d single-glyph, %d multi-glyph ligatures",
        len(deduped), len(deduped_multi),
    )
    ft_font.close()
    return deduped, deduped_multi


def save_ligatures_cache(
    ligatures: list[tuple[list[str], str]],
    output_path: Path,
) -> None:
    """Save single-glyph ligatures in JSON format: [[components], replacement]."""
    data = [entry for entry in ligatures]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0, ensure_ascii=True)
    LOG.info("Wrote %d ligatures to %s", len(data), output_path)


def save_multi_glyph_cache(
    multi_ligatures: list[tuple[list[str], list[str]]],
    output_path: Path,
) -> None:
    """Save multi-glyph ligatures in JSON format: [[components], [glyph1, glyph2]]."""
    data = [entry for entry in multi_ligatures]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0, ensure_ascii=True)
    LOG.info("Wrote %d multi-glyph ligatures to %s", len(data), output_path)


def load_multi_glyph_cache(cache_path: Path) -> list[tuple[list[str], list[str]]]:
    """Load multi-glyph ligatures from JSON cache."""
    with open(cache_path, encoding="utf-8") as f:
        raw = json.load(f)
    out: list[tuple[list[str], list[str]]] = []
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        comps, repls = entry[0], entry[1]
        if not comps or not isinstance(repls, list) or len(repls) < 2:
            continue
        out.append((list(comps), list(repls)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate flattened ligature cache from Apple Color Emoji TTC.",
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
        help="Path to Apple Color Emoji.ttc",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(".ligatures.json"),
        help="Output JSON path (default: .ligatures.json)",
    )
    parser.add_argument(
        "--multi-output",
        type=Path,
        default=Path(".ligatures-multi.json"),
        help="Output JSON path for multi-glyph ligatures (default: .ligatures-multi.json)",
    )
    parser.add_argument(
        "--font-number",
        type=int,
        default=0,
        help="Font index in TTC (default: 0)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if not args.input.exists():
        LOG.error("Input not found: %s", args.input)
        return 1

    ligatures, multi_ligatures = generate_flattened_ligatures(args.input, args.font_number)
    if not ligatures and not multi_ligatures:
        LOG.error("No ligatures generated")
        return 1

    if ligatures:
        save_ligatures_cache(ligatures, args.output)
    if multi_ligatures:
        save_multi_glyph_cache(multi_ligatures, args.multi_output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
