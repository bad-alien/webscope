# WebScope CLI - Quick Reference

WebScope is a Python CLI tool that crawls web applications and generates detailed analysis reports with screenshots, DOM snapshots, and LLM-generated descriptions.

## Installation

```bash
# From the project root
pip install -e webscope/
# or
pip install -r webscope/requirements.txt
```

## Usage

```bash
# Basic crawl
python -m webscope https://example.com

# Advanced options
python -m webscope https://example.com \
  --depth 5 \
  --max-pages 100 \
  --output ./reports \
  --no-ai \
  --headed \
  --delay 2.0 5.0 \
  --verbose
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `url` | str | required | Target URL to crawl |
| `--depth` | int | 3 | Maximum crawl depth |
| `--max-pages` | int | 20 | Maximum pages to crawl |
| `--output` | path | `./webscope_report` | Output directory |
| `--no-ai` | flag | disabled | Skip LLM analysis |
| `--headless` | flag | enabled | Run browser headless |
| `--headed` | flag | - | Show browser window |
| `--delay` | float float | 1.0 3.0 | Delay range (min max) |
| `--verbose` | flag | disabled | Verbose logging |

## Exit Codes

- `0` - Success
- `1` - Error (invalid input, crash)
- `130` - Interrupted by user (Ctrl+C)

## Output

Reports are saved to the output directory:
```
webscope_report/
├── report.md                    # Main markdown report
└── screenshots/
    ├── capture_0001.png        # Viewport screenshot
    ├── capture_0001_full.png   # Full-page screenshot
    ├── capture_0002.png
    └── ...
```

## Module Structure

- **cli.py** - CLI entry point with argument parsing
- **models.py** - Data models (CrawlConfig, PageResult, Report, etc.)
- **utils.py** - Utility functions (URL normalization, logging, etc.)
- **stealth.py** - Human-like browser behavior (Bézier curves, delays)
- **crawler.py** - BFS crawl with link discovery
- **interactor.py** - Interactive element exploration
- **capturer.py** - Screenshots and DOM snapshots
- **analyzer.py** - LLM analysis (Claude API)
- **reporter.py** - Markdown report generation

## Key Features

✅ **Human-like Behavior** - Gaussian delays, Bézier mouse movements, realistic scrolling
✅ **Anti-Detection** - User-Agent rotation, viewport randomization, stealth masking
✅ **Comprehensive Capture** - Full-page screenshots, DOM snapshots, style extraction
✅ **Smart Interaction** - Automatic button/link discovery and exploration
✅ **LLM Analysis** - Claude-powered description of UI components and design
✅ **Detailed Reports** - Markdown with screenshots, component analysis, technical patterns

## Environment

Set your Anthropic API key for AI analysis:
```bash
export ANTHROPIC_API_KEY=your-key-here
python -m webscope https://example.com
```

## Examples

### Quick scan
```bash
python -m webscope https://example.com --depth 2 --max-pages 10
```

### Deep analysis
```bash
python -m webscope https://example.com --depth 5 --max-pages 50 --output ./deep_analysis
```

### Debug mode (show browser)
```bash
python -m webscope https://example.com --headed --verbose --delay 2.0 5.0
```

### No AI analysis
```bash
python -m webscope https://example.com --no-ai
```

## Troubleshooting

**Browser crashes:**
- Reduce `--max-pages` or `--depth`
- Add longer `--delay` ranges
- Try `--headed` to see what's happening

**Timeout errors:**
- Increase delay range: `--delay 3.0 10.0`
- Reduce max-pages: `--max-pages 10`

**API rate limits:**
- Set longer delay range
- Reduce concurrent operations
- Check `ANTHROPIC_API_KEY` is set

**No screenshots captured:**
- Check output directory permissions
- Verify `--output` directory exists
- Check disk space

## For Developers

### Adding new options

Edit `cli.py` `parse_args()` function:
```python
parser.add_argument(
    '--my-option',
    type=str,
    default='value',
    help='Description'
)
```

### Testing

```bash
# Test help
python -m webscope --help

# Test invalid URL
python -m webscope "not a url"

# Test with verbose logging
python -m webscope https://example.com --verbose

# Test with Ctrl+C
python -m webscope https://example.com --headed
# Then press Ctrl+C
```

### Data Models

Import from `webscope.models`:
```python
from webscope.models import CrawlConfig, PageResult, Report
```

### Utilities

Import from `webscope.utils`:
```python
from webscope.utils import normalize_url, setup_logging, ensure_dir
```

## Performance Targets

- Startup time: < 50ms
- Memory usage: < 50MB baseline
- Pages per minute: 2-5 (with human-like delays)

## License

WebScope © 2025

## Support

For issues or feature requests, check the architecture specification at `.agents/architecture.md`
