# Storage Cleaner — design

Date: 2026-11-22
Status: awaiting approval

## Goal

A personal iPhone app that finds what is safe to delete and frees real space on a
nearly full iPhone 13 (128 GB, iOS 27.0.1). Photos and videos (~30 GB) are the main
target. WhatsApp (~10 GB) and other apps are handled by a guided checklist, because
iOS does not let one app read or delete another app's data.

Success: the app shows, per category, how many GB can be reclaimed, lets the user
review and delete in a few taps, and the phone ends up with meaningfully more free
space without losing anything the user wanted to keep.

## What iOS allows (and does not)

| Area | Possible from an app? | How |
|---|---|---|
| Photo library: list, measure, delete | Yes, with full Photos permission | PhotoKit |
| Find duplicates / similar shots | Yes, on device | Vision feature prints |
| Shrink large videos | Yes | AVFoundation HEVC re-encode |
| Media WhatsApp saved into Photos | Yes | The "WhatsApp" album in Photos |
| WhatsApp's own storage (chats, in-app media) | No | Sandbox. Cleaned inside WhatsApp |
| Other apps' storage, System Data | No | Sandbox. Cleaned in Settings |
| Empty "Recently Deleted" | No | User does it in Photos |

Deleting through PhotoKit always shows an iOS confirmation and moves items to
Recently Deleted for 30 days. Space is only freed once Recently Deleted is emptied.
The app says so after every delete.

## Approaches considered

1. **Native iOS app (SwiftUI + PhotoKit + Vision), Claude for judgment calls — chosen.**
   The only approach that can both see the library and delete from it.
2. **Mac-side analyzer** (plug the phone in, analyze a backup or the camera roll, print
   a report). Can show WhatsApp per-chat sizes from a backup, but cannot delete
   anything, and a backup needs ~100 GB free on a Mac that has 29 GB. Rejected.
3. **Cross-platform (Expo / React Native).** Still needs Xcode, weaker access to
   Vision and PhotoKit, no benefit for one iPhone. Rejected.

## Features

### Dashboard
Device used / free space, total reclaimable found so far, one card per category with
item count and size, and a scan progress indicator.

### Cleanup categories (all on device, free, no network)
- **Large videos** — sorted by size, largest first.
- **Screen recordings**
- **Screenshots**
- **WhatsApp media in Photos** — contents of the "WhatsApp" album.
- **Exact duplicates** — identical content; keep one.
- **Similar photos** — near-identical shots taken close together; keep the best.
- **Bursts** — keep the picked frame, drop the rest.

Each category opens a grid with sizes, select all / none, a running "selected: X GB"
total, and a Delete button.

### Smart Review (Claude)
For categories where size and metadata cannot decide (screenshots, WhatsApp images,
optionally the rest of the library in chunks), the app sends small thumbnails to the
Claude API and gets back, per photo: `delete` / `keep` / `unsure`, a kind (meme or
forward, greeting forward, throwaway screenshot, receipt or ticket, document or ID,
personal photo, accidental or blurry, other) and a one-line reason.

- Prompt biases toward **keep**: people, documents, IDs, receipts, tickets, anything
  personal are kept. Only clear junk is marked delete.
- `delete` verdicts are pre-selected, `unsure` and `keep` are not. The user reviews
  before anything is deleted.
- Opt-in per run. Before each run the app shows how many photos will be sent and an
  estimated cost (measured with the token-counting endpoint on the first batch).
- Thumbnails only (long edge ~512 px), never originals, never videos.
- Verdicts are cached on device so nothing is sent or billed twice.
- Model: `claude-opus-5-5` by default, with Sonnet 5.5 and Haiku 5.5 selectable in
  Settings for cheaper bulk runs.
- API key is typed into Settings and stored in the iOS Keychain. It is never in the
  repo.

### Video compression
Re-encode a large video to HEVC 1080p, save the copy with the original date and
location, verify it (playable, same duration), then delete the original. Shows
before / after size. Videos that exist only in iCloud are skipped.

### Storage guide
A checklist for what the app cannot touch: empty Recently Deleted; WhatsApp →
Settings → Storage and Data → Manage Storage (and turning off auto-download and
Save to Photos); Settings → General → iPhone Storage (offload unused apps, Messages
attachments, apps with bloated caches); Safari website data; downloaded music,
podcasts and offline video; iCloud Photos "Optimize iPhone Storage".

## Safety rules

- Nothing is deleted without an explicit tap plus the iOS system confirmation.
- Favorites are never pre-selected.
- In a duplicate or similar group, at least one item is always kept. Best =
  favorite > edited > higher resolution > larger file > earlier date.
- Scanning never downloads iCloud originals onto the phone.
- Compression deletes the original only after the new copy is saved and verified.

## Architecture

```
StorageCleaner.xcodeproj
StorageCleaner/                 app target: SwiftUI views + system glue
  App/                          entry point, navigation
  Features/                     Dashboard, Category, SimilarGroups, SmartReview,
                                Compress, Guide, Settings
  Services/                     PhotoLibrary, SizeIndex, FeaturePrints,
                                VideoCompressor, ClaudeClient, Keychain
Packages/CleanerCore/           pure Swift, no PhotoKit, tested with `swift test`
  Models                        MediaItem, CleanupCategory, CleanupGroup, Verdict
  Rules                         category classification from metadata
  Grouping                      duplicate grouping, similarity clustering, best-pick
  Selection                     selection state and reclaimable-size math
  Claude                        request building, response parsing, cost estimate
  Formatting                    byte and duration formatting
```

The boundary: `CleanerCore` takes plain values (`MediaItem`, feature vectors, JSON)
and returns decisions. The app target converts `PHAsset` to `MediaItem`, runs
Vision / AVFoundation / network, and performs deletes. Core logic is therefore
testable on the Mac in seconds without a simulator.

Data flow: PhotoKit fetch → `MediaItem`s → SizeIndex fills in byte sizes (cached on
disk by asset id + modification date) → Rules and Grouping produce `CleanupGroup`s →
UI selection → PhotoKit delete request.

Deployment target iOS 17.0. No third-party dependencies. The Claude API is called
over HTTPS with URLSession (there is no official Swift SDK), using structured
outputs for the verdict JSON.

## Error handling

- Photos permission denied or limited → explain why full access is needed, link to
  Settings.
- Size lookup fails for an asset → item is listed with unknown size, excluded from
  totals.
- Claude errors: 401 → "check API key"; 429 / 5xx / network → retry with backoff,
  then pause the run with a Resume button; refusal or malformed batch → those photos
  become `unsure`. Completed batches are kept.
- Compression fails or verification fails → original is untouched, partial output
  removed.
- User cancels the iOS delete confirmation → selection is preserved.

## Testing

- `CleanerCore`: unit tests written first for rules, grouping, best-pick, selection
  math, Claude response parsing and formatting.
- App: build and run in the simulator with seeded photos, screenshots, duplicates
  and videos; check each flow with screenshots.
- Final check on the real phone.

## Build order

Small commits, pushed after each step.

1. Core models, formatting, category rules.
2. App shell, dashboard, device storage, Photos permission.
3. Library scan, size index, category screens, delete flow.
4. Duplicates and similar photos.
5. Smart Review with Claude.
6. Video compression.
7. Storage guide, polish, install instructions.

## Environment constraints

- This Mac has Xcode 26.3 on macOS 26.0. Its newest simulator is iOS 26.3.
- The phone runs iOS 27.0.1. Matching it (simulator and device install) needs
  Xcode 27, which needs macOS 26.6 or later.
- Plan: develop and verify on the iOS 26.3 simulator now. Before installing on the
  phone, the owner updates macOS and Xcode and signs in to Xcode with an Apple ID;
  then the simulator is switched to iOS 27 and the app is installed over a cable.
- A free Apple ID works; the app then needs re-installing every 7 days.

## Out of scope

App Store release, iPad layout, Android, deleting inside WhatsApp or other apps,
automatic deletion without review, analysing video content with Claude.
