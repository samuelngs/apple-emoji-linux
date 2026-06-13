# Test fixtures

One PNG per emoji. The font render test loads each fixture and compares it to what Chromium actually draws. Use **96 ppem** when extracting so it matches the 96 ppem strike in the build recipes.

Add fixtures with `extract.py`:

```bash
python extract.py --emoji 1F600 --ppem 96 --output tests/fixtures/1f600.png
python extract.py --emoji 1F389 --ppem 96 --output tests/fixtures/1f389.png
python extract.py --emoji 2764 --ppem 96 --output tests/fixtures/2764.png
```

Filename = lowercase hex codepoint (`1f600.png`, `2764.png`, etc.). The test finds every `*.png` here whose name is a valid hex codepoint. It composites the fixture on white before comparing (so transparent background is fine). You can pass `--similarity` when running the test to change the pass threshold (default 0.80).
