# Getting Started with Kindle Highlights Sync

Quick guide to install and use Kindle Highlights Sync.

---

## Installation

### Requirements
- Python 3.10+
- Chrome browser
- uv package manager (recommended)

### Install
```bash
git clone <repo-url>
cd kindle-highlights-sync

# With uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Verify
```bash
uv run kindle-sync --version
```

---

## Quick Start

### 1. Login
```bash
# Opens browser for Amazon login
uv run kindle-sync login

# With specific region
uv run kindle-sync login --region uk

# Headless mode (no browser window)
uv run kindle-sync login --headless
```

**What happens:**
1. Chrome browser opens
2. You log in through Amazon's website
3. Session cookies saved automatically
4. Browser closes

### 2. Sync Highlights
```bash
# Sync all books and highlights
uv run kindle-sync sync

# Full sync (re-download everything)
uv run kindle-sync sync --full

# Sync specific books
uv run kindle-sync sync --books B01N5AX61W,B07EXAMPLE
```

### 3. Export
```bash
# Export to Markdown (default)
uv run kindle-sync export ~/my-highlights

# Export to JSON
uv run kindle-sync export ~/output --format json

# Export to CSV
uv run kindle-sync export ~/output --format csv
```

### 4. View & Manage
```bash
# List all books
uv run kindle-sync list

# Show book details
uv run kindle-sync show B01N5AX61W

# Check status
uv run kindle-sync status

# Logout
uv run kindle-sync logout
```

---

## Common Workflows

### Daily Sync
```bash
uv run kindle-sync sync
uv run kindle-sync export ~/Documents/highlights
```

### First-Time Setup
```bash
uv run kindle-sync login --region uk
uv run kindle-sync sync --full
uv run kindle-sync export ~/kindle-notes
```

### Export Single Book
```bash
uv run kindle-sync list | grep "Atomic"
uv run kindle-sync export ~/output --books B01N5AX61W --format markdown
```

---

## Configuration

### Database Location
Default: `~/.kindle-sync/highlights.db`

Override:
```bash
uv run kindle-sync --db /custom/path.db sync
```

### Supported Regions

| Code | Amazon Site |
|------|-------------|
| `global` | amazon.com |
| `uk` | amazon.co.uk |
| `germany` | amazon.de |
| `japan` | amazon.co.jp |
| `india` | amazon.in |
| `spain` | amazon.es |
| `italy` | amazon.it |
| `france` | amazon.fr |

### Export Templates

Built-in: `default`, `simple`, `detailed`

Custom templates: Place in `~/.kindle-sync/templates/`

---

## Tips

### Automate Daily Sync (macOS/Linux)
```bash
# Add to crontab
crontab -e

# Run daily at 9 AM
0 9 * * * cd ~/kindle-highlights-sync && uv run kindle-sync sync
```

### Backup Database
```bash
cp ~/.kindle-sync/highlights.db ~/.kindle-sync/backup-$(date +%Y%m%d).db
```

### Search Highlights
```bash
sqlite3 ~/.kindle-sync/highlights.db
```
```sql
SELECT b.title, h.text 
FROM highlights h 
JOIN books b ON h.book_asin = b.asin 
WHERE h.text LIKE '%productivity%';
```

### Custom Template
```bash
mkdir -p ~/.kindle-sync/templates
cat > ~/.kindle-sync/templates/simple.md.j2 << 'EOF'
# {{ book.title }}
{% for highlight in highlights %}
- {{ highlight.text }}
{% endfor %}
EOF

uv run kindle-sync export ~/output --template simple
```

---

## Troubleshooting

### "Login failed"
- **Try non-headless**: `uv run kindle-sync login --no-headless`
- **Check region**: Use `--region uk` for amazon.co.uk
- **2FA enabled**: May require manual intervention

### "Session expired"
```bash
uv run kindle-sync logout
uv run kindle-sync login
```
Sessions expire after ~7 days.

### "No books found"
- Ensure you have Kindle highlights on Amazon
- Try: `uv run kindle-sync sync --full`
- Check region is correct

### "Database locked"
```bash
# Kill any stuck processes
ps aux | grep kindle-sync
killall kindle-sync
```

---

## File Locations

```
~/.kindle-sync/
├── highlights.db          # Your database
├── exports/               # Default export location
└── templates/             # Custom templates
    └── mytemplate.md.j2
```

---

## Next Steps

- Read [Specification.md](Specification.md) for technical details
- Check [CHANGELOG.md](../CHANGELOG.md) for updates
- Report issues on GitHub

---

## Quick Reference

```bash
# Authentication
kindle-sync login [--region REGION] [--headless]
kindle-sync logout

# Sync
kindle-sync sync [--full] [--books ASINS]

# Export
kindle-sync export DIR [--format FORMAT] [--template NAME]

# Info
kindle-sync list [--sort FIELD]
kindle-sync show ASIN
kindle-sync status

# Global options
--db PATH          Custom database path
--verbose, -v      Detailed output
--quiet, -q        Minimal output
```

---

**Happy highlighting!** 📚
