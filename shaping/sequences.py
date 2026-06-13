from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VS16 = 0xFE0F
VS15 = 0xFE0E


@dataclass(frozen=True)
class SequenceRecord:
    normalized_sequence: tuple[int, ...]
    raw_sequences: tuple[tuple[int, ...], ...]
    source: str
    status: str = "supported"
    notes: str | None = None


@dataclass(frozen=True)
class SequenceRule:
    components: tuple[int, ...]
    replacement: str
    normalized_sequence: tuple[int, ...]
    raw_sequence: tuple[int, ...]


def load_sequence_inventory(
    sequence_files: tuple[Path, ...] | list[Path],
    project_sequence_files: tuple[Path, ...] | list[Path] = (),
) -> list[SequenceRecord]:
    grouped: dict[tuple[int, ...], dict[str, object]] = {}
    for path in sequence_files:
        _read_sequence_file(path, "unicode", grouped)
    for path in project_sequence_files:
        _read_sequence_file(path, "project", grouped)

    records: list[SequenceRecord] = []
    for normalized in sorted(grouped):
        data = grouped[normalized]
        raw_sequences = sorted(data["raw_sequences"])  # type: ignore[arg-type]
        sources = sorted(data["sources"])  # type: ignore[arg-type]
        records.append(
            SequenceRecord(
                normalized_sequence=normalized,
                raw_sequences=tuple(raw_sequences),
                source="+".join(sources),
            ),
        )
    return records


def normalize_sequence(sequence: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(cp for cp in sequence if cp != VS16)


def sequence_glyph_name(sequence: tuple[int, ...]) -> str:
    return "seq." + "_".join(f"{cp:04X}" for cp in sequence)


def format_sequence(sequence: tuple[int, ...]) -> str:
    return " ".join(f"{cp:04X}" for cp in sequence)


def _read_sequence_file(
    path: Path,
    source: str,
    grouped: dict[tuple[int, ...], dict[str, object]],
) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Sequence file not found: {path}")
    with path.open(encoding="utf-8") as f:
        for line in f:
            for raw_sequence in _parse_sequence_line(line):
                normalized = normalize_sequence(raw_sequence)
                if not normalized:
                    continue
                entry = grouped.setdefault(
                    normalized,
                    {"raw_sequences": set(), "sources": set()},
                )
                raw_sequences = entry["raw_sequences"]
                sources = entry["sources"]
                assert isinstance(raw_sequences, set)
                assert isinstance(sources, set)
                raw_sequences.add(raw_sequence)
                raw_sequences.add(normalized)
                sources.add(source)


def _parse_sequence_line(line: str) -> list[tuple[int, ...]]:
    body = line.split("#", 1)[0].strip()
    if not body:
        return []
    codepoints = body.split(";", 1)[0].strip()
    if not codepoints:
        return []

    parts = codepoints.split()
    if len(parts) == 1 and ".." in parts[0]:
        start_text, end_text = parts[0].split("..", 1)
        start = int(start_text, 16)
        end = int(end_text, 16)
        if end < start:
            return []
        return [(cp,) for cp in range(start, end + 1)]

    try:
        sequence = tuple(int(part, 16) for part in parts)
    except ValueError:
        return []
    if VS15 in sequence:
        return []
    return [sequence]
