# MediaWiki Sync (mw_sync)

> 🌐 **Language / Idioma:** [Español](README.md) | **English** · **User Manual:** [Español](MANUAL_USO_MEDIAWIKI_SYNC.md) | [English](MANUAL_USO_MEDIAWIKI_SYNC.en.md)

Native Python suite for high-performance bidirectional synchronization between **MediaWiki** servers and local documentation repositories in **Markdown (.md)** format.

Engineered with a **zero external dependencies** architecture (runs exclusively on the Python 3.13+ standard library) and optimized for enterprise environments featuring two-tier authentication, custom SSL certificate inspection, and multithreaded concurrency.

---

## Contents

1. [Key Features](#key-features)
2. [Architecture and Components](#architecture-and-components)
3. [Requirements and Installation](#requirements-and-installation)
4. [Environment Configuration (.env)](#environment-configuration-env)
5. [CLI Usage Guide](#cli-usage-guide)
   - [Concurrent Incremental Download](#concurrent-incremental-download)
   - [Uploading Changes and Conflict Control](#uploading-changes-and-conflict-control)
   - [Diff Preview](#diff-preview)
   - [Offline Sanitization and Normalization](#offline-sanitization-and-normalization)
   - [Empty Pages Management](#empty-pages-management)
6. [Usage as a Python Library](#usage-as-a-python-library)
7. [Complete CLI Parameter Reference](#complete-cli-parameter-reference)
8. [Security and Best Practices](#security-and-best-practices)
9. [Test Suite](#test-suite)
10. [License](#license)

---

## Key Features

- **Zero External Dependencies:** 100% powered by Python standard library modules (`urllib`, `re`, `concurrent.futures`, `json`, `hashlib`, `argparse`, `ssl`, `locale`). No mandatory `pip install`, facilitating frictionless deployment in isolated or high-security environments.
- **Two-Tier Authentication:** Native and concurrent support for:
  - Perimeter web layer (HTTP Basic Auth on Apache/Nginx servers or reverse proxies).
  - MediaWiki application layer (Action API with `login` and `csrf` tokens using an in-memory cookie jar).
- **Intelligent Incremental Download by Revision (`revid`):** Batched queries (50 articles per call) comparing remote server revisions against the local `.sync_state.json` file. Only new or modified articles are transferred, reducing sync operations with hundreds of articles to just seconds.
- **Multithreaded Concurrency:** Configurable parallel download of pages and multimedia files using `ThreadPoolExecutor`.
- **Strict Conflict Prevention (`baserevid`):** Validates that local edits originate from the latest revision on the server before publishing. If a concurrent remote modification is detected:
  - Immediately downloads the current server content to a backup file with `.servidor.conflict` suffix.
  - Aborts the publication by default to prevent accidental overwrites.
  - Allows forcing the publication via interactive console confirmation or non-interactively with `--yes`.
- **High-Fidelity Bidirectional Conversion Engine:**
  - *HTML -> Markdown:* Strips residual tables of contents (`__TOC__`), `[edit]` links, formats pipe tables (`|`), normalizes nested lists with accurate indentation, and rewrites internal hyperlinks for local relative offline browsing (`./Article.md`).
  - *Markdown -> Wikitext:* Transforms headers (`#` to `=`), bold (`**` to `'''`), italics (`*` to `''`), lists (`-`/`*` to `*`, `1.` to `#`), code blocks, and image syntax without polluting wiki semantics.
- **Unified Contextual Diff Mode:** Inspects the generated Wikitext against current remote server content in unified diff format before publishing.
- **Mass Offline Sanitizer:** Repairs collections of Markdown files by eliminating syntactic artifacts, broken HTML entities, and incorrect indentation.
- **Full Native Internationalization (i18n):** Complete bilingual support (English and Spanish) across the CLI, help text, interactive prompts, and documentation, with automatic system locale detection and explicit `--lang` / `MW_LANG` selection.

---

## Architecture and Components

The project is structured as a standard Python package `mw_sync` managed with Poetry:

```text
mediawiki-sync/
├── pyproject.toml              # Package definition and Poetry configuration (PEP 621)
├── LICENSE                     # GNU General Public License v3 (GPL-3.0)
├── MANUAL_USO_MEDIAWIKI_SYNC.md# Detailed user manual (Spanish)
├── MANUAL_USO_MEDIAWIKI_SYNC.en.md # Detailed user manual (English)
├── README.md                   # Technical documentation (Spanish)
├── README.en.md                # Technical documentation (English)
├── .env.example                # Environment configuration template
├── .env                        # Local variables and credentials (ignored by Git)
├── .gitignore                  # Exclusion of credentials, dist/ and temporary files
├── .github/
│   └── workflows/
│       └── e2e-mediawiki.yml   # CI/CD: Unit test matrix and live E2E Docker tests
├── mw_sync/                    # Core application package
│   ├── __init__.py             # Public API exports, version, and i18n helpers
│   ├── __main__.py             # Modular entry point (`python3 -m mw_sync`)
│   ├── cli.py                  # CLI argument parsing and terminal orchestration
│   ├── client.py               # HTTP/HTTPS client for MediaWiki Action API
│   ├── config.py               # Configuration loading and credential resolution
│   ├── downloader.py           # Multithreaded incremental download engine
│   ├── empty_pages.py          # Remote empty page detection and management
│   ├── i18n.py                 # Native zero-dependency internationalization module
│   ├── state.py                # Local state persistence (.sync_state.json)
│   ├── uploader.py             # Upload engine, diff previews, and conflict management
│   └── converters/
│       ├── html_to_md.py       # HTML to Markdown converter with sanitization
│       ├── md_to_wikitext.py   # Markdown to standard Wikitext converter
│       └── sanitizer.py        # Mass offline Markdown collection repair
└── tests/
    ├── test_converters.py      # Format converter unit tests
    ├── test_uploader.py        # Upload, title extraction, and conflict resolution tests
    ├── test_empty_pages.py     # Empty page handling and remote deletion tests
    ├── test_collisions.py      # Filename collisions and redirect filter tests
    ├── test_config_discovery.py# Auto-discovery of .env and directory resolution tests
    ├── test_i18n.py            # Internationalization, locale detection, and parity tests
    └── test_live_wiki.py       # Live E2E integration tests against Docker MediaWiki
```

---

## Requirements and Installation

### Requirements

- Python 3.13 or higher.
- No mandatory external dependencies (native architecture relying strictly on standard Python modules).

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/jrubioh1/mediawiki_sync.git
   cd mediawiki_sync
   ```

2. Prepare the configuration file with your credentials:
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

### Installation and Packaging Options

#### Option 1: Direct Installation from PyPI (Recommended)
```bash
pip install mediawiki-sync

# Executable commands available globally or in your virtualenv:
mw-sync --help
mediawiki-sync --help
```

#### Option 2: Local Development with Poetry
Installs the project in editable mode registering the `mw-sync` and `mediawiki-sync` commands:
```bash
poetry install

# Run commands inside the environment:
poetry run mw-sync --help
# Or activate the virtual environment:
source .venv/bin/activate
mw-sync --help
```

#### Option 3: Local Wheel Installation (.whl)
Builds the standard distributable package and installs it:
```bash
# Build package (in dist/):
poetry build

# Install the generated wheel:
pip install dist/mediawiki_sync-1.2.0-py3-none-any.whl

# Terminal commands available globally:
mw-sync --help
mediawiki-sync --help
```

#### Option 4: Optional High-Performance HTTP Acceleration
If you want network acceleration via `requests` / `urllib3` connection pooling:
```bash
pip install "mediawiki-sync[fast-http]"
# Or locally:
pip install ".[fast-http]"
```

#### Option 5: Direct Module Execution
If running directly from the repository clone without package installation:
```bash
python3 -m mw_sync --help
```

---

## Environment Configuration (.env and System Variables)

`mw_sync` allows configuring connections, credentials, and runtime parameters in both local development and production environments (Docker, Kubernetes, GitHub Actions, systemd, etc.).

### Precedence Hierarchy

The configuration engine resolves values applying the following hierarchy (from highest to lowest priority):

1. **CLI Parameters:** Explicit command-line arguments (e.g., `--url`, `--threads 16`, `--lang en`).
2. **System Environment Variables:** Variables exported in the OS, Docker container, or CI/CD pipeline (e.g., `export MW_URL=...`).
3. **Local `.env` File:** Loaded from the working directory (without overwriting existing system variables).
4. **Application Defaults:** Default fallbacks built into the codebase.

---

### Local Development vs Production

- **Local Development:** Copy `.env.example` to `.env` in the root of your project and configure values. The `.env` file is excluded in `.gitignore` to prevent credential leakage.
- **Production / Containers / CI/CD:** No `.env` file needed. Define system environment variables (`MW_URL`, `MW_WIKI_USER`, etc.) in your orchestrator (Docker / Kubernetes Secrets), systemd service units, or CI/CD secrets.
- **Documentation Directory Resolution (`MW_OUTPUT_DIR` / `--dir`):**
  - **No need to run `mw-sync` inside the documentation folder.** The tool automatically discovers the path from `MW_OUTPUT_DIR` or the `--dir` (`-o`) flag.
  - **Absolute vs Relative Paths:** Relative paths (e.g., `MW_OUTPUT_DIR=./wiki_docs`) resolve relative to the directory containing the project `.env` file. Absolute paths (e.g., `MW_OUTPUT_DIR=/var/docs/wiki`) work identically regardless of the current working directory.
  - The `.sync_state.json` state file is automatically stored inside `<OUTPUT_DIR>/.sync_state.json`.

---

### Multi-Wiki Management Pattern

When managing multiple independent MediaWiki servers (e.g., Internal Wiki, Public Wiki, Project Wiki), the recommended practice is to structure separate project folders each with its own `.env`:

```text
my_wikis/
├── internal_wiki/
│   ├── .env               # Internal wiki configuration and credentials
│   └── wiki_docs/         # Local documentation and .sync_state.json
├── public_wiki/
│   ├── .env               # Public wiki configuration and credentials
│   └── wiki_docs/
└── projects_wiki/
    ├── .env               # Projects wiki configuration
    └── wiki_docs/
```

**Multi-site workflow:**
```bash
# Option 1: Switch to the project directory
cd my_wikis/internal_wiki
mw-sync --upload

# Option 2: Execute from anywhere using --dir (Auto-discovery of .env)
mw-sync --upload --dir /path/to/my_wikis/public_wiki
```

---

### Complete Environment Variables Reference (`MW_*`)

| Environment Variable | Description | Default Value | Mapped CLI Argument |
| :--- | :--- | :--- | :--- |
| `MW_URL` | Full URL of the MediaWiki Action API (`api.php`) | `https://wiki.example.com/api.php` | `--url` |
| `MW_HTTP_USER` | HTTP Basic Auth username (Apache/Nginx/Reverse Proxy) | `""` (empty) | `--http-user` |
| `MW_HTTP_PASS` | HTTP Basic Auth password | `""` (empty) | `--http-password` |
| `MW_WIKI_USER` | MediaWiki account username (Action API) | `""` (empty) | `--wiki-user` |
| `MW_WIKI_PASS` | MediaWiki account password | `""` (empty) | `--wiki-password` |
| `MW_USER` | Legacy username fallback | `""` (empty) | `--user` |
| `MW_PASS` | Legacy password fallback | `""` (empty) | `--password` |
| `MW_VERIFY_SSL` | Enable strict SSL certificate verification (`true`/`false`/`1`/`0`/`yes`/`no`) | `false` | `--verify-ssl` |
| `MW_CA_BUNDLE` | Path to CA Bundle file (`.crt`/`.pem`) for corporate/self-signed certs | `None` | `--ca-bundle` |
| `MW_TIMEOUT` | Maximum HTTP request timeout in seconds | `10.0` | HTTP Client |
| `MW_USER_AGENT` | Custom `User-Agent` header sent with requests | `MediaWikiSync/3.0 (Python; BiDirectional)` | HTTP Client |
| `MW_OUTPUT_DIR` | Local directory for Markdown files and images | `./wiki_docs` | `--dir`, `-o` |
| `MW_THREADS` | Number of concurrent threads for parallel downloads | `8` | `--threads`, `-t` |
| `MW_LANG` | Output language for CLI and messages (`es` / `en`) | `es` | `--lang`, `-l` |
| `MW_EDIT_SUMMARY` | Default revision summary when publishing to MediaWiki | `Actualizado desde local...` | `--summary` |
| `MW_TEST_LIVE` | *(Testing)* Enable live E2E test suite against MediaWiki (`1`/`0`) | `0` | Test Suite |
| `MW_TEST_LIVE_URL` | *(Testing)* Action API endpoint for live E2E tests | `http://localhost:8080/api.php` | Test Suite |
| `MW_TEST_WIKI_USER` | *(Testing)* Admin user for live E2E tests | `TestAdmin` | Test Suite |
| `MW_TEST_WIKI_PASS` | *(Testing)* Admin password for live E2E tests | `TestPass123` | Test Suite |

---

## CLI Usage Guide

The tool can be executed via terminal commands (`mw-sync` or `mediawiki-sync`), or as a module via `python3 -m mw_sync`.

### Language Selection
```bash
# View help in English:
mw-sync --lang en --help

# View help in Spanish:
mw-sync --lang es --help

# Run operations with English output:
mw-sync --lang en
```

### Concurrent Incremental Download
By default, running `mw-sync` without arguments starts an incremental download into the configured directory:
```bash
# Standard incremental download (8 parallel threads):
mw-sync

# Adjust concurrency level:
mw-sync --threads 16

# Force re-download of all articles ignoring local state:
mw-sync --force

# Download article text only, skipping multimedia files:
mw-sync --no-images
```

### Uploading Changes and Conflict Control
The `--upload` mode scans the local documentation directory, calculates SHA-256 hashes against `.sync_state.json`, and detects modified or newly created articles:
```bash
# Dry-run simulation to review changes without touching the server:
mw-sync --upload --dry-run

# Upload all modified local files:
mw-sync --upload

# Upload a specific Markdown article:
mw-sync --upload --file ./wiki_docs/User_Manual.md

# Upload an image to the wiki media repository:
mw-sync --upload --file ./wiki_docs/images/network_diagram.png

# Skip interactive prompts during conflict resolution (forced overwrite):
mw-sync --upload --force --yes
```

#### Conflict Resolution Protocol
If a concurrent remote edit is detected:
1. The engine never overwrites remote content silently.
2. It downloads the current remote version to `<file>.servidor.conflict`.
3. It prompts you in the console to inspect differences and choose whether to cancel or force upload.

### Diff Preview
Preview generated Wikitext against current MediaWiki content in unified diff format:
```bash
mw-sync --upload --diff --dry-run
```

### Offline Sanitization and Normalization
Clean local Markdown files, strip obsolete editing tags, fix broken formatting, and normalize internal links:
```bash
# Run real sanitization on local files:
mw-sync --sanitize

# Preview which files would be modified without touching disk:
mw-sync --sanitize --dry-run
```

### Empty Pages Management
```bash
# Interactively manage empty pages recorded in state:
mw-sync --empty-pages

# Batch create local templates for empty pages:
mw-sync --empty-pages --empty-action create-md

# Delete empty pages on the remote MediaWiki (action=delete):
mw-sync --empty-action delete-remote --yes

# Skip empty pages silently in automated pipelines:
mw-sync --empty-action ignore
```

---

## Usage as a Python Library

```python
from mw_sync import MediaWikiClient, ejecutar_descarga, markdown_a_wikitext, set_language

# Set language (es or en)
set_language("en")

# 1. Initialize client
cliente = MediaWikiClient(
    url="https://wiki.example.com/api.php",
    http_user="proxy_user",
    http_password="proxy_password",
    wiki_user="wiki_user",
    wiki_password="wiki_password",
    verify_ssl=True
)

# 2. Test connection and log in
connected, sitename = cliente.test_conexion()
if connected:
    print(f"Connected to {sitename}")
    ok_login, msg = cliente.login()
    print(msg)

# 3. Download articles
ejecutar_descarga(cliente, output_dir="./wiki_docs", max_hilos=4)

# 4. Convert Markdown to Wikitext
md_text = "# Main Section\n\nThis is a paragraph with **bold** text."
wikitext = markdown_a_wikitext(md_text)
print(wikitext)
```

---

## Complete CLI Parameter Reference

| Argument | Shorthand | Mapped Environment Variable | Description | Default Value |
| :--- | :--- | :--- | :--- | :--- |
| `--lang` | `-l` | `MW_LANG` | Console language (`es` = Spanish, `en` = English) | `es` (or system locale) |
| `--download` | `-dl` | N/A | Incremental download from MediaWiki to local Markdown | Active by default |
| `--upload` | `-up` | N/A | Upload local changes to MediaWiki | Disabled |
| `--sanitize` | | N/A | Run offline Markdown syntax sanitizer | Disabled |
| `--diff` | | N/A | Show contextual Wikitext difference preview | Disabled |
| `--dry-run` | | N/A | Simulate operations without writing to disk or server | Disabled |
| `--force` | `-f` | N/A | Force download or upload ignoring hashes | Disabled |
| `--yes` | `-y` | N/A | Answer 'yes' non-interactively to confirmations | Disabled |
| `--empty-pages` | | N/A | List and manage empty pages recorded in local state | Disabled |
| `--empty-action` | | N/A | Action for empty pages (`ask`, `create-md`, `delete-remote`, `ignore`) | `ask` |
| `--threads` | `-t` | `MW_THREADS` | Number of concurrent threads for parallel downloads | `8` |
| `--dir` | `-o` | `MW_OUTPUT_DIR` | Local documentation directory | `./wiki_docs` |
| `--file` | | N/A | Path to a single file (`.md` or image) to upload | `None` |
| `--no-images` | | N/A | Skip multimedia file synchronization | Disabled |
| `--summary` | | `MW_EDIT_SUMMARY` | Edit summary for MediaWiki revision history | `Actualizado desde local...` |
| `--url` | | `MW_URL` | MediaWiki `api.php` Action API endpoint URL | `https://wiki.example.com/api.php` |
| `--http-user` | | `MW_HTTP_USER` (or `MW_USER`) | HTTP Basic Auth username | `""` |
| `--http-password`| | `MW_HTTP_PASS` (or `MW_PASS`) | HTTP Basic Auth password | `""` |
| `--wiki-user` | | `MW_WIKI_USER` (or `MW_USER`) | MediaWiki username (Action API) | `""` |
| `--wiki-password`| | `MW_WIKI_PASS` (or `MW_PASS`) | MediaWiki password (Action API) | `""` |
| `--verify-ssl` | | `MW_VERIFY_SSL` | Enable strict SSL certificate verification | `false` |
| `--ca-bundle` | | `MW_CA_BUNDLE` | Path to custom CA Bundle file | `None` |

---

## Security and Best Practices

1. **Secrets Isolation:**
   The `.gitignore` file strictly excludes:
   - `.env` (credentials and passwords).
   - `wiki_docs/` (downloaded articles, media, and hash cache).
   - Conflict resolution files (`*.servidor.conflict`).
   - Virtual environments and cache files (`*.pyc`, `__pycache__`).

2. **TLS/SSL Verification:**
   In corporate networks with HTTPS inspection or self-signed certificates, avoid turning verification off (`MW_VERIFY_SSL=false`). Provide `--ca-bundle /path/to/cert.pem` instead.

3. **Concurrency and Collision Prevention:**
   The uploader validates CSRF tokens and enforces `baserevid` checks to guarantee that no remote modifications are overwritten unintentionally.

---

## Test Suite

```bash
# Run unit test suite:
python3 -m unittest discover tests

# Or with poetry:
poetry run python -m unittest discover tests
```

### Suite Coverage:
- `tests/test_converters.py`: Validates HTML -> Markdown and Markdown -> Wikitext bidirectional conversions, nested lists (`#`, `#*`), tables, relative links, and artifact cleanup (`__TOC__`, `[edit]`).
- `tests/test_uploader.py`: Validates metadata extraction from frontmatter / `#` titles and `baserevid` conflict detection.
- `tests/test_empty_pages.py`: Validates empty page handling, local template creation, `.sync_state.json` recording, and remote deletion (`action=delete`).
- `tests/test_i18n.py`: Validates native internationalization engine (ES/EN catalog parity, priority hierarchy, and boolean response parsing).
- `tests/test_live_wiki.py`: End-to-end integration tests executed in CI against a real Dockerized MediaWiki container.

---

## License

Distributed under the terms of the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. For details, see [LICENSE](LICENSE).
