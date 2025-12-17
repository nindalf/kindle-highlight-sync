# Getting Started with Kindle Highlights Sync

This guide will walk you through setting up and using Kindle Highlights Sync to download and export your Kindle highlights.

## Table of Contents

1. [Installation](#installation)
2. [First-Time Setup](#first-time-setup)
3. [Basic Usage](#basic-usage)
4. [Common Workflows](#common-workflows)
5. [Tips and Tricks](#tips-and-tricks)
6. [Next Steps](#next-steps)

---

## Installation

### Prerequisites

Before you begin, make sure you have:

- **Python 3.10 or higher** installed
  ```bash
  python --version  # Should show 3.10 or higher
  ```

- **uv package manager** (recommended) or pip
  ```bash
  # Install uv if you don't have it
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Chrome or Firefox browser** for authentication

### Step 1: Get the Code

```bash
# Clone the repository
git clone <repo-url>
cd kindle-highlights-sync
```

### Step 2: Install Dependencies

**Using uv (recommended)**:
```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows

# Install the package
uv pip install -e ".[dev]"
```

**Using pip**:
```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows

# Install the package
pip install -e ".[dev]"
```

### Step 3: Verify Installation

```bash
kindle-sync --version
```

You should see: `kindle-highlights-sync, version 0.1.0`

---

## First-Time Setup

### Step 1: Authenticate with Amazon

The first thing you need to do is authenticate with Amazon:

```bash
kindle-sync login
```

**What happens:**
1. A browser window opens showing Amazon's login page
2. Log in with your Amazon credentials
3. Once logged in, the window closes automatically
4. Your session is saved locally

**Output:**
```
Opening browser for Amazon login...
Please log in to your Amazon account.
✓ Login successful! Session saved.
```

**Tips:**
- Use `--region` if you use Amazon outside the US:
  ```bash
  kindle-sync login --region uk        # For amazon.co.uk
  kindle-sync login --region germany   # For amazon.de
  kindle-sync login --region japan     # For amazon.co.jp
  ```

- If you prefer not to see the browser window:
  ```bash
  kindle-sync login --headless
  ```

### Step 2: Sync Your First Highlights

Now download your books and highlights:

```bash
kindle-sync sync
```

**What happens:**
1. Connects to Amazon using your saved session
2. Downloads list of all your Kindle books
3. Downloads highlights for each book
4. Saves everything to local database

**Output:**
```
Syncing highlights from Amazon...
✓ Found 23 books
✓ Synced 156 highlights
✓ Database updated
```

**Where is the data?**
- Database: `~/.kindle-sync/highlights.db`
- This is a SQLite database containing all your books and highlights

### Step 3: Export Your Highlights

Export your highlights to readable files:

```bash
mkdir ~/my-kindle-highlights
kindle-sync export ~/my-kindle-highlights
```

**What happens:**
- Creates one Markdown file per book
- Files are named like: `Clear-Atomic-Habits.md`
- Each file contains the book's highlights

**Output:**
```
Exporting highlights...
✓ Exported 23 books to /Users/you/my-kindle-highlights
```

---

## Basic Usage

### Checking Status

See what's in your database:

```bash
kindle-sync status
```

**Output:**
```
Database: /Users/you/.kindle-sync/highlights.db
Last Sync: 2023-10-15 14:30:00
Total Books: 23
Total Highlights: 456
Session: Active (expires in 7 days)
```

### Listing Books

See all your synced books:

```bash
kindle-sync list
```

**Output:**
```
┌──────────────────────────────────┬─────────────────┬────────────┐
│ Title                            │ Author          │ Highlights │
├──────────────────────────────────┼─────────────────┼────────────┤
│ Atomic Habits                    │ James Clear     │ 42         │
│ The Pragmatic Programmer         │ Hunt & Thomas   │ 78         │
│ Deep Work                        │ Cal Newport     │ 31         │
└──────────────────────────────────┴─────────────────┴────────────┘
```

### Viewing a Specific Book

Get details about a book:

```bash
# First, get the book ID from list
kindle-sync list

# Then show details
kindle-sync show abc123
```

**Output:**
```
Title: Atomic Habits
Author: James Clear
ASIN: B01N5AX61W
Highlights: 42
Last Annotated: 2023-10-15

Recent highlights:
1. "You do not rise to the level of your goals..."
2. "Habits are the compound interest of self-improvement..."
3. "Every action you take is a vote for the type of person..."
```

---

## Common Workflows

### Workflow 1: Daily Sync and Export

If you highlight daily:

```bash
# Sync new highlights (incremental, fast)
kindle-sync sync

# Export to your notes folder
kindle-sync export ~/Documents/kindle-notes
```

**Why incremental?**
- Only downloads new/updated books
- Much faster than full sync
- Perfect for daily use

### Workflow 2: Export to Different Formats

Export highlights in various formats:

```bash
# Markdown (default, great for note-taking)
kindle-sync export ~/output --format markdown

# JSON (great for programmatic access)
kindle-sync export ~/output --format json

# CSV (great for spreadsheets)
kindle-sync export ~/output --format csv
```

### Workflow 3: Export Specific Books

Only export books you're currently reading:

```bash
# Find book IDs
kindle-sync list | grep "Atomic"

# Export just that book
kindle-sync export ~/reading --books abc123
```

### Workflow 4: Starting Fresh

If you want to re-download everything:

```bash
# Full sync (re-downloads all books)
kindle-sync sync --full
```

### Workflow 5: Using on Multiple Computers

**Computer 1 (main):**
```bash
kindle-sync login
kindle-sync sync
kindle-sync export ~/Dropbox/kindle-highlights
```

**Computer 2 (secondary):**
```bash
# Just use the exported files from Dropbox
# No need to login or sync
```

---

## Tips and Tricks

### Tip 1: Automate Daily Syncs

**On macOS/Linux (cron):**
```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 9 AM)
0 9 * * * /path/to/.venv/bin/kindle-sync sync && /path/to/.venv/bin/kindle-sync export ~/Documents/highlights
```

**On Windows (Task Scheduler):**
- Create a batch file with your commands
- Schedule it in Task Scheduler

### Tip 2: Backup Your Database

Your database contains all your synced data:

```bash
# Backup before major operations
cp ~/.kindle-sync/highlights.db ~/.kindle-sync/backup-$(date +%Y%m%d).db

# Or use a script
mkdir -p ~/.kindle-sync/backups
cp ~/.kindle-sync/highlights.db ~/.kindle-sync/backups/highlights-$(date +%Y%m%d).db
```

### Tip 3: Search Your Highlights

Use SQLite directly to search:

```bash
sqlite3 ~/.kindle-sync/highlights.db

# Search for highlights containing "productivity"
SELECT b.title, h.text 
FROM highlights h 
JOIN books b ON h.book_id = b.id 
WHERE h.text LIKE '%productivity%';
```

### Tip 4: Custom Export Templates

Create your own Markdown templates:

```bash
# Create templates directory
mkdir -p ~/.kindle-sync/templates

# Copy and modify a template
cat > ~/.kindle-sync/templates/mytemplate.md.j2 << 'EOF'
# {{ book.title }} by {{ book.author }}

{% for highlight in highlights %}
- {{ highlight.text }}
{% endfor %}
EOF

# Use your template
kindle-sync export ~/output --template mytemplate
```

### Tip 5: Combine with Other Tools

**With Obsidian:**
```bash
# Export directly to Obsidian vault
kindle-sync export ~/Obsidian/Kindle
```

**With Notion:**
```bash
# Export as JSON, then import to Notion
kindle-sync export ~/output --format json
# Then use Notion's import feature
```

### Tip 6: Session Management

Your session expires after ~7 days:

```bash
# Check if still authenticated
kindle-sync status

# If expired, re-login
kindle-sync logout
kindle-sync login
```

---

## Troubleshooting

### Issue: "Login failed"

**Possible causes:**
- Wrong region selected
- Two-factor authentication enabled
- Network issues

**Solutions:**
```bash
# Try with visible browser
kindle-sync login --no-headless

# Check region
kindle-sync login --region uk  # If you use amazon.co.uk
```

### Issue: "No books found"

**Check:**
- Do you have highlights in your Amazon Kindle account?
- Are you using the correct region?

**Try:**
```bash
# Full sync
kindle-sync sync --full

# Check status
kindle-sync status
```

### Issue: "Session expired"

**Solution:**
```bash
# Clear old session
kindle-sync logout

# Login again
kindle-sync login
```

### Issue: "Database locked"

**Cause:** Another process is using the database

**Solution:**
```bash
# Check for running processes
ps aux | grep kindle-sync

# Kill any stuck processes
killall kindle-sync

# Try again
kindle-sync sync
```

---

## Understanding File Locations

### Default Locations

```
~/.kindle-sync/                    # Main directory
├── highlights.db                  # Your database
├── templates/                     # Custom templates
│   └── mytemplate.md.j2
└── exports/                       # Default export location
    ├── Clear-Atomic-Habits.md
    └── Newport-Deep-Work.md
```

### Customizing Locations

```bash
# Use custom database location
kindle-sync --db /path/to/custom.db sync

# Export to custom location
kindle-sync export /path/to/output
```

---

## Next Steps

### Learn More

Now that you have the basics, explore:

1. **[Technical Specification](SPECIFICATION.md)** - Detailed technical design
2. **[Database Schema](DATABASE.md)** - Database structure and queries
3. **[API Documentation](API.md)** - Python API for advanced usage

### Advanced Usage

Try these advanced features:

```bash
# Export with different templates
kindle-sync export ~/output --template detailed

# List as JSON for scripting
kindle-sync list --format json | jq '.[] | .title'

# Sync only specific books
kindle-sync sync --books abc123,def456
```

### Integrate with Your Workflow

Ideas for integration:

- **Note-taking**: Export to Obsidian, Notion, or Evernote
- **Reading tracker**: Use database to track reading statistics
- **Sharing**: Export and share highlights with friends
- **Analysis**: Analyze your reading patterns with SQL queries

---

## Quick Reference

### Essential Commands

```bash
# Initial setup
kindle-sync login
kindle-sync sync

# Daily use
kindle-sync sync            # Update highlights
kindle-sync export ./output # Export to files

# Information
kindle-sync status          # Check status
kindle-sync list            # List books
kindle-sync show <id>       # Show book details

# Maintenance
kindle-sync logout          # Clear session
```

### Common Options

```bash
--db PATH              # Custom database location
--verbose, -v          # Detailed output
--quiet, -q            # Minimal output
--help                 # Show help
```

### Export Options

```bash
--format markdown|json|csv    # Output format
--template NAME               # Template name
--books ID1,ID2               # Specific books only
```

---

## Getting Help

If you need help:

1. **Check documentation**: Look in `docs/` folder
2. **Check status**: Run `kindle-sync status`
3. **Enable verbose**: Run with `-v` flag for details
4. **Open issue**: Report bugs on GitHub

---

**You're all set! Happy reading and highlighting!** 📚✨
