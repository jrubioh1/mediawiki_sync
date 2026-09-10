# User Manual: MediaWiki <-> Markdown Synchronizer (v3.1)

> 🌐 **Language / Idioma:** [Español](MANUAL_USO_MEDIAWIKI_SYNC.md) | **English** · **README:** [Español](README.md) | [English](README.en.md)

Native Python tool for high-performance bidirectional synchronization between **MediaWiki** servers and local files in **Markdown (.md)** format with multithreading support, intelligent incremental downloading, media assets synchronization, conflict control, and **HTTP Basic Auth** authentication (zero external dependencies).

---

## Table of Contents
1. [Key Features (v3.1)](#key-features-v31)
2. [Project Structure and Modules](#project-structure-and-modules)
3. [Execution Methods (CLI Command or Script)](#execution-methods-cli-command-or-script)
4. [Secure Configuration (.env)](#secure-configuration-env)
5. [Mode 1: Concurrent Incremental Download](#mode-1-concurrent-incremental-download)
6. [Mode 2: Upload and Conflict Control (--upload)](#mode-2-upload-and-conflict-control---upload)
7. [Mode 3: Offline File Sanitization (--sanitize)](#mode-3-offline-file-sanitization---sanitize)
8. [Mode 4: Empty Pages Management (--empty-pages)](#mode-4-empty-pages-management---empty-pages)
9. [Mode 5: Language Selection and Internationalization (i18n)](#mode-5-language-selection-and-internationalization-i18n)
10. [CLI Parameters Reference](#cli-parameters-reference)
11. [Test Suite](#test-suite)

---

## Key Features (v3.1)

* **Intelligent Incremental Download by `revid`:** Compares server revisions in batches of 50. Only downloads articles that have actually changed on the server, cutting synchronization time from minutes to just seconds.
* **Multithreaded Concurrent Download (`ThreadPoolExecutor`):** Parallelizes page and image downloads with `--threads` (default 8 threads), multiplying transfer speed by 10x.
* **Intelligent Empty Page Management:** Detects contentless pages on the wiki without raising false download errors. Choose interactively or via CLI whether to create empty local `.md` templates to fill in, delete them on the remote server (`action=delete`), or skip them while silencing redundant retries.
* **Robust Conversion Without Artifacts:**
  * Completely removes tables of contents (TOC), `[edit]` links, and orphaned asterisks.
  * Maps internal MediaWiki links to local relative `./Article.md` files for fluid offline reading (Obsidian, VS Code, Typora).
  * Converts nested lists preserving indentation levels (`*`, `**`, `***`, `#`, `##`).
* **Edit Conflict Prevention (`baserevid`):** During upload, validates whether another user modified the page on the server to prevent accidental overwrites. If a conflict is detected, automatically downloads a backup copy `<file>.servidor.conflict`.
* **Zero External Dependencies:** Built strictly on native Python libraries (`urllib`, `re`, `concurrent.futures`, `json`, `argparse`, `locale`). No third-party packages or heavy frameworks required.
* **Modern Packaging with Poetry:** Distributable as a standard `.whl` package, configurable in `pyproject.toml`, and providing executable console commands (`mw-sync` and `mediawiki-sync`).
* **Hardened Security:** Credentials loaded automatically from `.env` (ignored by Git) with interactive fallback prompts when missing.
* **Full Native Internationalization (i18n):** Complete English and Spanish support with automatic system locale detection and explicit `--lang` / `MW_LANG` selection.

---

## Project Structure and Modules

```text
mediawiki-sync/
├── pyproject.toml              # Poetry package configuration (PEP 621)
├── LICENSE                     # GNU GPL v3 License
├── MANUAL_USO_MEDIAWIKI_SYNC.md# User manual (Spanish)
├── MANUAL_USO_MEDIAWIKI_SYNC.en.md # User manual (English)
├── README.md                   # General technical documentation (Spanish)
├── README.en.md                # General technical documentation (English)
├── .env.example                # Environment variables template
├── .env                        # Local credentials (IGNORED BY GIT)
├── .gitignore                  # Protection of credentials, dist/ and temporary files
├── .github/
│   └── workflows/
│       └── e2e-mediawiki.yml   # CI/CD: Unit test matrix and live E2E tests
├── mw_sync/                    # Core modular native package
│   ├── __init__.py             # Public exports and version
│   ├── __main__.py             # Modular entry point (python3 -m mw_sync)
│   ├── cli.py                  # Unified command-line interface
│   ├── client.py               # MediaWiki Action API client (retries, tokens, deletion)
│   ├── config.py               # .env loader and default configuration
│   ├── downloader.py           # Multithreaded incremental download engine
│   ├── empty_pages.py          # Empty pages control and management module
│   ├── i18n.py                 # Native internationalization engine (es / en)
│   ├── state.py                # State persistence in .sync_state.json and SHA-256 hashes
│   ├── uploader.py             # Upload engine and conflict detection
│   └── converters/
│       ├── html_to_md.py       # HTML -> Clean Markdown converter
│       ├── md_to_wikitext.py   # Markdown -> Standard Wikitext converter
│       └── sanitizer.py        # Mass offline cleaner and sanitizer
├── tests/
│   ├── test_converters.py      # Format converter unit tests
│   ├── test_uploader.py        # Upload and conflict unit tests
│   ├── test_empty_pages.py     # Empty pages management and deletion unit tests
│   ├── test_collisions.py      # Filename collisions and redirect filter tests
│   ├── test_config_discovery.py# Auto-discovery of .env and directory resolution tests
│   ├── test_i18n.py            # Internationalization, parity, and locale tests
│   └── test_live_wiki.py       # Live E2E tests against Docker MediaWiki
└── wiki_docs/                  # Local documentation directory (ignored by Git)
    ├── .sync_state.json        # Hash and revision ID registry
    ├── 00_INDICE_MEDIAWIKI.md  # Navigable general index
    ├── *.md                    # Individual Markdown articles
    └── images/                 # Downloaded images and multimedia files
```

---

## Execution Methods (CLI Command or Module)

The synchronizer can be launched in any of the following modes:

1. **Short terminal command (Recommended for daily interactive use):**
   ```bash
   mw-sync --help
   ```
2. **Long terminal command (Recommended for scripts / automation):**
   ```bash
   mediawiki-sync --help
   ```
3. **Direct Python module execution:**
   ```bash
   python3 -m mw_sync --help
   ```

---

## Secure Configuration (.env and Environment Variables)

`mw_sync` supports configuration via a local `.env` file or directly through **operating system environment variables**, facilitating smooth integration on development workstations, production servers, Docker containers, and CI/CD pipelines.

### Precedence Hierarchy

The order of priority for resolving parameters (from highest to lowest) is:

1. **CLI Parameters:** Arguments such as `--url`, `--threads 16`, or `--lang en` override all other sources.
2. **System Environment Variables:** Defined in the OS environment (`export MW_URL=...`, Docker `ENV`, Kubernetes Secrets, GitHub Actions).
3. **Local `.env` File:** Loaded from `.env` in the working directory (without overriding existing system variables).
4. **Default Values:** Default settings defined internally in the configuration module.

### Local Development vs Production

* **Local Development:** Copy `.env.example` as `.env` into the root of the project and fill in your credentials. The `.env` file is excluded in `.gitignore` so secrets are never pushed to Git.
* **Production Environments (Docker, CI/CD, Cron, Systemd):** No `.env` file is required. Set environment variables directly in the container or process environment:
  ```bash
  export MW_URL="https://wiki.company.com/api.php"
  export MW_WIKI_USER="sync_bot"
  export MW_WIKI_PASS="SecretPassword123"
  mw-sync --upload
  ```
* **Directory Location and Execution with `MW_OUTPUT_DIR` / `--dir`:**
  - **No need to navigate (`cd`) into the output folder:** The synchronizer automatically detects the directory from `MW_OUTPUT_DIR` or the `--dir` (`-o`) CLI parameter.
  - Specifying an **absolute path** (e.g., `MW_OUTPUT_DIR=/home/user/wiki_documents`) works identically regardless of your terminal working directory.
  - Specifying a **relative path** (e.g., `MW_OUTPUT_DIR=./wiki_docs`) in `.env` resolves relative to the `.env` file location.
  - The state file `.sync_state.json` is always stored inside the configured output directory (`<OUTPUT_DIR>/.sync_state.json`).

---

### Multi-Wiki Management Pattern

To manage multiple independent MediaWiki servers (e.g., Internal Wiki, Public Wiki, Customer Wiki), the recommended structure is to create separate project directories, each with its own `.env`:

```text
my_wikis/
├── internal_wiki/
│   ├── .env               # MW_URL=https://internal.company.com/api.php
│   └── wiki_docs/         # Markdown files and .sync_state.json
├── public_wiki/
│   ├── .env               # MW_URL=https://public.company.com/api.php
│   └── wiki_docs/
└── customer_wiki/
    ├── .env               # MW_URL=https://customers.company.com/api.php
    └── wiki_docs/
```

**Workflow:**
```bash
# Option 1: Switch to the project directory
cd my_wikis/internal_wiki
mw-sync --upload

# Option 2: Execute from anywhere using --dir (Auto-discovery of .env)
mw-sync --upload --dir /home/user/my_wikis/customer_wiki
```

---

### Download (`--download`) and Upload (`--upload`) Scenarios

> [!NOTE]
> The `--download` (or `-dl`) flag is **optional**. Incremental download is the **default mode** whenever `--upload` is not specified. Therefore, `mw-sync` and `mw-sync --dir /path` execute downloads automatically.

#### Scenario 1: Standard Execution (using `cd` inside the project)
```bash
cd my_wikis/customer_wiki
mw-sync          # Downloads into ./wiki_docs/
mw-sync --upload # Uploads changes from ./wiki_docs/
```

#### Scenario 2: Multi-Wiki pointing to project root (`--dir /path/to/project`)
```bash
# Executes from any directory without cd:
mw-sync --dir /home/user/my_wikis/customer_wiki
mw-sync --upload --dir /home/user/my_wikis/customer_wiki
```
*Behavior:* Automatically discovers and loads `.env` from `customer_wiki/` and syncs into `/home/user/my_wikis/customer_wiki/wiki_docs/`.

#### Scenario 3: Pointing directly to `wiki_docs` (`--dir /path/to/project/wiki_docs`)
```bash
mw-sync --dir /home/user/my_wikis/customer_wiki/wiki_docs
mw-sync --upload --dir /home/user/my_wikis/customer_wiki/wiki_docs
```
*Behavior:* Finds the `.env` in the parent directory (`customer_wiki/`) and operates directly inside `wiki_docs/` without nesting.

#### Scenario 4: Custom folder in `.env` (`MW_OUTPUT_DIR=./custom_docs`)
```bash
mw-sync --dir /home/user/my_wikis/customer_wiki
```
*Behavior:* Resolves `MW_OUTPUT_DIR` relative to `.env`, syncing into `customer_wiki/custom_docs/`.

#### Scenario 5: Arbitrary directory without `.env` (CI/CD / Docker)
```bash
export MW_URL="https://wiki.company.com/api.php"
export MW_WIKI_USER="ci_bot"
export MW_WIKI_PASS="secret"
mw-sync --dir /var/docs/manuals
```
*Behavior:* Stores `.md` files directly in `/var/docs/manuals/` without creating a `wiki_docs` subfolder.

#### Scenario 6: Flat structure in project (`MW_OUTPUT_DIR=.`)
```ini
# In .env:
MW_OUTPUT_DIR=.
```
```bash
mw-sync --dir /home/user/my_wikis/flat_wiki
```
*Behavior:* Stores `.md` files, images, and `.sync_state.json` directly at the root of `flat_wiki/`.

---

### Summary Matrix: When is `wiki_docs` created vs using the directory directly?

| Setup / Parameter | Is `wiki_docs/` created? | Markdown Destination | Rule / Reason |
| :--- | :--- | :--- | :--- |
| **New project without `MW_OUTPUT_DIR`** | **Yes (by convention)** | `<project>/wiki_docs/` | Standard convention isolates Markdown from project root files. |
| **Project with `MW_OUTPUT_DIR=.`** | **No (direct)** | `<project>/` (root) | Dot `.` explicitly targets the project root. |
| **Project with `MW_OUTPUT_DIR=./custom`** | **No (direct)** | `<project>/custom/` | Honors custom user-specified directory name. |
| **Project with existing `.md` in root** | **No (direct)** | `<project>/` (root) | Automatically detects existing root Markdown files and preserves layout. |
| **Direct folder without `.env`** (`--dir /var/docs`) | **No (direct)** | `/var/docs/` | Not a project directory; treated as direct destination. |
| **Path ending in `wiki_docs`** (`--dir .../wiki_docs`) | Already that directory | `.../wiki_docs/` | Avoids nesting `wiki_docs/wiki_docs`. |

---

### Complete Environment Variables Catalog (`MW_*`)

| Environment Variable | Description | Default Value | Mapped CLI Parameter |
| :--- | :--- | :--- | :--- |
| `MW_URL` | MediaWiki Action API endpoint (`api.php`) | `https://wiki.example.com/api.php` | `--url` |
| `MW_HTTP_USER` | HTTP Basic Auth username (Apache / Reverse Proxy) | `""` (empty) | `--http-user` |
| `MW_HTTP_PASS` | HTTP Basic Auth password | `""` (empty) | `--http-password` |
| `MW_WIKI_USER` | MediaWiki account username (Action API) | `""` (empty) | `--wiki-user` |
| `MW_WIKI_PASS` | MediaWiki account password | `""` (empty) | `--wiki-password` |
| `MW_USER` | Legacy fallback username | `""` (empty) | `--user` |
| `MW_PASS` | Legacy fallback password | `""` (empty) | `--password` |
| `MW_VERIFY_SSL` | Strict SSL verification (`true`/`false`/`1`/`0`) | `false` | `--verify-ssl` |
| `MW_CA_BUNDLE` | Path to custom CA Bundle (`.crt`/`.pem`) | `None` | `--ca-bundle` |
| `MW_TIMEOUT` | Request timeout in seconds | `10.0` | HTTP Client |
| `MW_USER_AGENT` | Network `User-Agent` header | `MediaWikiSync/3.0 (Python; BiDirectional)` | HTTP Client |
| `MW_OUTPUT_DIR` | Local directory for Markdown documents | `./wiki_docs` | `--dir`, `-o` |
| `MW_THREADS` | Concurrent threads for parallel downloads | `8` | `--threads`, `-t` |
| `MW_LANG` | Console and message language (`es` / `en`) | `es` (or system locale) | `--lang`, `-l` |
| `MW_EDIT_SUMMARY` | Default edit summary for MediaWiki history | `Actualizado desde local...` | `--summary` |
| `MW_TEST_LIVE` | *(Testing)* Enable live E2E tests (`1`/`0`) | `0` | Test Suite |
| `MW_TEST_LIVE_URL` | *(Testing)* Endpoint for live E2E tests | `http://localhost:8080/api.php` | Test Suite |
| `MW_TEST_WIKI_USER` | *(Testing)* Admin user for live E2E tests | `TestAdmin` | Test Suite |
| `MW_TEST_WIKI_PASS` | *(Testing)* Admin password for live E2E tests | `TestPass123` | Test Suite |

---

## Mode 1: Concurrent Incremental Download

Synchronizes content from MediaWiki to your local folder. Only new or modified articles on the server are downloaded.

```bash
# 1. Fast incremental download (8 parallel threads):
mw-sync

# 2. Specify more concurrent threads (e.g., 16 threads):
mw-sync --threads 16

# 3. Force full re-download of the entire wiki:
mw-sync --force

# 4. Download text only, skipping images:
mw-sync --no-images

# 5. Run with English output:
mw-sync --lang en
```

---

## Mode 2: Upload and Conflict Control (--upload)

Detects locally modified `.md` or image files and publishes them to MediaWiki:

```bash
# 1. DRY-RUN Simulation: check what would be uploaded without touching the server:
mw-sync --upload --dry-run

# 2. Preview Wikitext differences before uploading:
mw-sync --upload --diff --dry-run

# 3. Upload all detected local changes:
mw-sync --upload

# 4. Upload a single specific Markdown file:
mw-sync --upload --file ./wiki_docs/User_Manual.md

# 5. Upload a single image file:
mw-sync --upload --file ./wiki_docs/images/diagram.png

# 6. Force conflict resolution without interactive prompts:
mw-sync --upload --force --yes
```

---

## Mode 3: Offline File Sanitization (--sanitize)

Batch repairs local Markdown collections (strips residual `[edit]` anchors, broken formatting, and orphan `****` marks):

```bash
# Sanitize all .md files in ./wiki_docs:
mw-sync --sanitize

# Preview sanitization without modifying files on disk:
mw-sync --sanitize --dry-run
```

---

## Mode 4: Empty Pages Management (--empty-pages)

When a remote MediaWiki page lacks content, the tool records it in `.sync_state.json` without raising false errors, offering 3 resolution options:

1. **Create local `.md` templates:** Generates a file with frontmatter and `# Title`, ready to fill offline and upload later.
2. **Delete from remote server (`action=delete`):** Removes pages from MediaWiki (requires deletion rights).
3. **Skip / Ignore:** Records the page as skipped to avoid re-downloading or reporting errors until modified remotely.

```bash
# 1. Interactively manage detected empty pages:
mw-sync --empty-pages

# 2. Batch create local .md templates without prompts:
mw-sync --empty-pages --empty-action create-md

# 3. Download and automatically create templates for empty pages:
mw-sync --empty-action create-md

# 4. Download and force deletion of empty pages on remote MediaWiki:
mw-sync --empty-action delete-remote --yes

# 5. Download and silently skip empty pages (unattended CI/CD):
mw-sync --empty-action ignore
```

---

## Mode 5: Language Selection and Internationalization (i18n)

MediaWiki Sync includes a native internationalization engine built entirely on Python's standard library (zero external dependencies like Babel or Gettext). It provides full bilingual support in **Spanish** (`es`) and **English** (`en`).

### 1. Language Resolution and Precedence

The engine determines the interface language using the following precedence hierarchy (highest to lowest priority):

1. **Explicit CLI argument:** `--lang <es|en>` or `-l <es|en>`.
2. **Environment variable or `.env` file:** `MW_LANG=<es|en>`.
3. **Operating system locale detection:** Environment variables `LC_ALL`, `LC_MESSAGES`, `LANG` or `locale.getlocale()`.
4. **Default fallback:** Spanish (`es`).

### 2. Bilingual Console Help (--help)

Language detection is evaluated early before parsing remaining arguments. This allows viewing CLI help in either language:

```bash
# View complete help in English:
mw-sync --lang en --help
# Or shorthand:
mw-sync -l en -h

# View complete help in Spanish:
mw-sync --lang es --help
```

### 3. Running Commands with English Output

Any operation (`--download`, `--upload`, `--sanitize`, etc.) can be run with English output:

```bash
# Incremental download in English:
mw-sync --lang en

# Upload with diff preview in English:
mw-sync --upload --diff --lang en

# Offline file sanitization in English:
mw-sync --sanitize --lang en
```

### 4. Bilingual Interactive Prompts

When an operation requests console confirmation (e.g., resolving upload conflicts or deleting empty pages), the boolean response parser accepts affirmations in both languages:
* **Affirmative:** `s`, `si`, `sí`, `y`, `yes` (case-insensitive).
* **Negative / Cancel:** `n`, `no`, or pressing `Enter` for the default action.

### 5. Persistent Configuration in `.env`

To permanently configure English without passing `--lang en` on every command, add the following line to your `.env` file:

```ini
# Console interface language (es = Spanish, en = English)
MW_LANG=en
```

---

## CLI Parameters Reference

| Parameter | Shorthand | Mapped Variable (`MW_*`) | Description | Default Value |
| :--- | :--- | :--- | :--- | :--- |
| `--lang` | `-l` | `MW_LANG` | Output language (`es` / `en`) | `es` (or system locale) |
| `--download` | `-dl` | N/A | Incremental download mode (server -> local) | Active by default |
| `--upload` | `-up` | N/A | Upload mode (local -> server) | False |
| `--sanitize` | | N/A | Cleans and sanitizes local Markdown files | False |
| `--diff` | | N/A | Displays unified Wikitext preview | False |
| `--dry-run` | | N/A | Simulates operations without altering server or disk | False |
| `--force` | `-f` | N/A | Forces download/upload skipping hash/revid checks | False |
| `--yes` | `-y` | N/A | Answers 'yes' non-interactively to confirmations | False |
| `--empty-pages` | | N/A | Lists and manages empty pages in local state | False |
| `--empty-action` | | N/A | Action for empty pages (`ask`, `create-md`, `delete-remote`, `ignore`) | `ask` |
| `--threads` | `-t` | `MW_THREADS` | Number of concurrent download threads | `8` |
| `--dir` | `-o` | `MW_OUTPUT_DIR` | Local documentation directory | `./wiki_docs` |
| `--file` | | N/A | Specific `.md` or image file to upload | `None` |
| `--no-images` | | N/A | Skips multimedia file download or upload | False |
| `--include-redirects` | | `MW_INCLUDE_REDIRECTS` | Includes MediaWiki redirect pages in synchronization | False |
| `--summary` | | `MW_EDIT_SUMMARY` | Revision summary message for MediaWiki history | Configured in env |
| `--url` | | `MW_URL` | MediaWiki `api.php` endpoint URL | Configured in env |
| `--http-user` | | `MW_HTTP_USER` (or `MW_USER`) | HTTP Basic Auth username | Configured in env |
| `--http-password` | | `MW_HTTP_PASS` (or `MW_PASS`) | HTTP Basic Auth password | Configured in env |
| `--wiki-user` | | `MW_WIKI_USER` (or `MW_USER`) | MediaWiki account username (Action API) | Configured in env |
| `--wiki-password` | | `MW_WIKI_PASS` (or `MW_PASS`) | MediaWiki account password | Configured in env |
| `--verify-ssl` | | `MW_VERIFY_SSL` | Enable strict SSL certificate verification | Configured in env |
| `--ca-bundle` | | `MW_CA_BUNDLE` | Path to corporate CA certificate bundle | `None` |

---

## Test Suite

To validate the conversion engines, packaging, and end-to-end sync flows:

```bash
# Run native unit tests (zero dependencies):
python3 -m unittest discover tests

# Or using Poetry:
poetry run python -m unittest discover tests
```

### Suite Coverage:
- `tests/test_converters.py`: Bidirectional conversions HTML/Markdown/Wikitext, tables, links, and nested lists.
- `tests/test_uploader.py`: Metadata extraction, `baserevid` conflict detection, and automatic backup.
- `tests/test_empty_pages.py`: Empty page detection, local template generation, and remote deletion.
- `tests/test_collisions.py`: Filename collisions resolution and redirect filtering.
- `tests/test_config_discovery.py`: Auto-discovery of `.env` files and directory resolution.
- `tests/test_i18n.py`: Internationalization catalog parity, interpolation, and locale detection.
- `tests/test_live_wiki.py`: Real E2E live integration tests against a Dockerized MediaWiki instance.
