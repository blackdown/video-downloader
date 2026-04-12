# Changelog

## Unreleased

### Added
- **Mux stream support** — `stream.mux.com` HLS URLs now detected and downloaded (covers Patreon video posts)
- **Source page URL field** — optional "Source page URL" input in the URL bar; sent as HTTP `Referer` header, required for Mux streams with `playback_restriction_id` origin restrictions
- **Login profile for authenticated downloads** — detection profile cookies (Chrome session) are now extracted and passed to yt-dlp via a Netscape cookies file, enabling downloads from Skillshare, Patreon, and other members-only sites without needing the browser open
- **Setup Profile moved to Settings panel** — no longer buried inside the Detect Videos dialog
- **Browser-based video detection** (`Detect Videos` button) — launches Chrome via Playwright with stealth to scan network requests for video streams on any page
- **playwright-stealth v2 support** — `Stealth().hook_playwright_context()` API used to reduce bot-detection fingerprinting during video scanning
- **Default save folder** set to the current user's `Videos` folder

### Changed
- Profile setup now launches a plain Chrome subprocess (no Playwright/CDP) so login pages load without bot-detection interference
- Cookie extraction prefers detection profile cookies over live browser extraction; falls back gracefully when neither is available
- `CommandBuilder` now accepts `referer_url` and adds `--referer` to yt-dlp for direct streams
- `VimeoDownloader` now accepts and threads `referer_url` through to command building
- Simplified auth/settings UI — removed browser dropdown (login profile handles auth instead)
- URL input strips all whitespace including embedded newlines (handles copy-paste of multi-line JWT tokens)
- Detect Videos dialog directs user to Settings for profile setup rather than hosting its own Setup button

### Fixed
- Chrome profile detection marker (`.profile-ready`) now always written even if the browser closes with an exception, preventing repeated setup prompts
- Cookie domain matching fixed for `.domain.com` style entries (e.g. `.patreon.com` now correctly matches `www.patreon.com`)
- yt-dlp no longer receives `--cookies-from-browser chrome` when browser cookie extraction failed (was causing auth errors on subsequent downloads)
- `--disable-dev-shm-usage` flag removed (Linux-only, caused errors on Windows/Edge)
- Playwright now uses `executable_path` instead of `channel` to reliably open Chrome rather than Edge

### Dependencies
- Added `playwright-stealth >= 2.0.0`
- Added `cryptography >= 41.0.0` (AES-256-GCM cookie decryption for detection profile)
