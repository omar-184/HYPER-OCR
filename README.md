# HYPER-OCR

Turn scanned PDFs and photos of pages into:

- a **searchable PDF**: the original pages, unchanged, with invisible text on top, so you can search, select and copy;
- a **Markdown file**, made with [Microsoft MarkItDown](https://github.com/microsoft/markitdown), with the text, headings, figures, captions and tables in reading order;
- an **`Images` folder** with every picture, chart and figure cut out of the pages;
- a **`Tables` folder** with each table as its own Word file (`.docx`).

> **Check every number.** OCR misreads numbers, and it does so with full confidence: in testing `5.3` became `53` and `5 mg` became `5 9`. Every number HYPER-OCR reads is unverified, including text you copy from the searchable PDF. Compare each one with the original page before you use it. Each Word table includes a picture of the original table for exactly this, and the results screen says so every time.

Everything runs on your computer. There is no internet connection at run time, no cloud AI and no account. The interface follows Apple's design language (grouped lists, a large title that folds into a frosted bar, segmented controls and spring animations that respond to your hand). It is in English and Arabic, with light and dark appearance, and works in a phone browser too.

![HYPER-OCR in light appearance, with four files ready](docs/screenshot-light.png)

![Results in dark appearance, three files converted separately](docs/screenshot-dark.png)

![On a phone, light and dark](docs/screenshot-phone.png)

## What you get

Click **Download All (ZIP)** and you get one ZIP file:

```
My scan_HYPER-OCR.zip
└── My scan/
    ├── My scan_searchable.pdf      original pages + invisible text + bookmarks from the headings
    ├── My scan.md                  the whole document as Markdown
    ├── Images/
    │   ├── page-001_figure-01.png
    │   └── page-002_figure-01.png
    └── Tables/
        └── Table-01_page-002.docx  one Word file per table
```

Convert several files **each separately** and the ZIP holds one such folder per file, named `HYPER-OCR_3-documents.zip` for three files. **Combine into one** makes a single document from all of them, in the order you set, named after the first file (`IMG_001_combined`).

The Markdown links to its pictures (`![Figure 1 …](Images/page-001_figure-01.png)`) and to each table's Word file, so the folder works as a whole when you unzip it.

Each Word table keeps merged cells, and repeats its header row on every printed page. Arabic tables run right to left. Each file also has the table's caption, the page it came from, a warning that the numbers are unverified and, always, a picture of the original table to check them against.

## Install

You need the internet **once**, during setup. After that the app never goes online.

### Windows 10 or 11

1. Download this folder (on GitHub: **Code → Download ZIP**) and unzip it somewhere, for example in `Documents`.
2. Double-click **`setup-windows.bat`**. It installs, where missing:
   - Python 3.12;
   - Tesseract OCR;
   - the app's packages;
   - the English and Arabic language files.

   If Windows installs Python, it asks you to run the setup once more.
3. Double-click **`start-windows.bat`**. Your browser opens HYPER-OCR at `http://127.0.0.1:8765`. Keep the black window open while you use the app; close it to stop.

### macOS

1. Install [Homebrew](https://brew.sh) if you don't have it.
2. Open Terminal in this folder and run `./setup.sh`.
3. Start the app by double-clicking **`start-mac.command`**. The first time, macOS may block it: right-click it, choose **Open**, then **Open** again.


### Linux

Run `./setup.sh`, then `./start.sh`. On Ubuntu, setup installs Tesseract with `apt` and asks for your password.

## Use

1. **Choose files.** Drop them anywhere on the window, or click the box to pick them. You can mix:
   - scanned PDFs;
   - photos and scans of pages: JPG, PNG, TIFF (multi-page too), WebP, BMP and **HEIC/HEIF from an iPhone**.

   Photos are turned the right way up from their camera orientation, and their page size comes from the picture's resolution (or an A4-sized guess when it has none).
2. **With two or more files, choose how to convert them.**
   - **Combine into One**: one searchable PDF, Markdown and ZIP with every page, in the order of the list. Drag the ☰ handle to reorder, or focus it and press ↑ / ↓.
   - **Each Separately**: every file gets its own searchable PDF, Markdown, `Images` and `Tables`, all in one ZIP.
3. **Text recognition.**
   - *Engine*: **Automatic** is Tesseract. (The experimental GPU engine is off; see [The OCR engine](#the-ocr-engine).)
   - *Resolution*: 300 dpi suits most scans. Choose 400 dpi for tiny print, or 200 dpi for speed.
   - *Languages*: tick every language that appears. Tesseract reads only the languages you tick.
   - *Output*: leave page headers, footers and page numbers out of the Markdown. (Every Word table always includes a picture of the original table.)
4. **Convert.** The card shows the page being scanned, the file it belongs to, and the time left. You can cancel at any time.
5. **Your files.** Download the ZIP, or single files: the searchable PDF, the Markdown, each table. When you converted several files separately, tap a file to open its results.

The **ⓘ** button opens **About**: the version, **Software Update**, Automatic / Light / Dark appearance, and what this computer can run. Your choices (appearance, language, engine, resolution, languages, mode) are remembered in this browser.

![Results in Arabic, dark theme](docs/screenshot-arabic-dark.png)

## Updating

You download HYPER-OCR once. After that, updates replace only the app's own files: Python, the installed packages, Tesseract, the language files and the Unlimited-OCR model all stay, so nothing large is downloaded again.

**In the app:** click **ⓘ**, then **Check** next to *Software Update*. If a newer version exists, the button becomes **Update**. Click it and HYPER-OCR downloads the new version from GitHub, installs it, restarts itself and reloads the page. (The button waits while a conversion is running.)

**Without the app:** double-click **`update-windows.bat`**, or run `./update.sh` on macOS and Linux. Add `--check` to only check, or `--yes` to update without being asked.

What an update does:

1. Asks GitHub for the latest **published release** of HYPER-OCR and compares its version with yours. Work in progress on a branch is never installed; nor are drafts or pre-releases.
2. Downloads the release's `HYPER-OCR-<version>.zip` and checks it against the SHA-256 published with it. A download that doesn't match is refused.
3. If the new version needs different packages, installs them first. If that fails (no internet, a package missing for your Python), it stops there and nothing has changed.
4. Copies the new version's files over the app and removes app files it no longer has. Only the app's own files and folders are touched: `.venv`, `models`, `tessdata`, `tesseract`, `.backup` and any folder of your own stay as they are.
5. Keeps the files it replaced in `.backup/<version>/` (only the last update's backup is kept). If anything fails while copying, they are put back.

The GPU packages are never downloaded unless the experimental GPU engine is switched on.

**Publishing a release (for the maintainer).** Commit, set the version in `hyperocr/__init__.py`, run `python tools/make_release.py`, then create a GitHub Release tagged `v<version>` on that commit with the two files from `dist/` attached. Nothing reaches users before that.

Updating is the only thing in HYPER-OCR that goes online, and only when you click it. It runs as a separate program; the converter itself stays offline. The app is started by a small supervisor, so after an update it comes back on its own at the same address.

## The OCR engine

HYPER-OCR reads pages with **Tesseract**, on the computer's processor: 2 to 5 seconds a page on a laptop. Its layout comes from HYPER-OCR's own image analysis: bordered tables (merged cells included), figures, headings and captions.

**Unlimited-OCR (Baidu) is experimental and switched off.** On graphics cards that can't really run its 3-billion-parameter model, it looked available and *Automatic* chose it, so conversions never finished. Setup no longer offers it and the app doesn't show it. It can only be switched on by hand, for testing on a capable NVIDIA card:

```
set HYPEROCR_GPU=1                       (macOS and Linux: export HYPEROCR_GPU=1)
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python -m pip install -r requirements-gpu.txt
.venv\Scripts\python -m hyperocr.download_model
```

then start the app from that same window. The model is saved in `models/Unlimited-OCR` and loaded with Hugging Face's offline mode on. A local vLLM or SGLang server also needs `HYPEROCR_GPU=1`, plus `HYPEROCR_OCR_SERVER=http://127.0.0.1:10000`.

**Already installed the GPU add-on and want the space back (about 10 GB)?** HYPER-OCR never deletes it for you. With the app closed, in this folder:

```
.venv\Scripts\python -m pip uninstall -y torch torchvision transformers
rmdir /s /q models\Unlimited-OCR          (macOS and Linux: rm -rf models/Unlimited-OCR)
```

## Languages

Setup adds English and Arabic. To add more Tesseract languages (one-time download):

```
.venv\Scripts\python -m hyperocr.languages add fra deu spa      (French, German, Spanish)
.venv\Scripts\python -m hyperocr.languages                      (list what is installed)
```

Use Tesseract's codes: `fas` Persian, `urd` Urdu, `tur` Turkish, `chi_sim` Chinese, and so on. Add `--best` for the larger, slower, sometimes more accurate models. The new languages appear as checkboxes the next time you start the app.

## Privacy

- The server listens on `127.0.0.1` only, so other computers on your network cannot reach it. It also refuses requests addressed to any other host name, and changes that don't carry the app's own header, so a website open in another tab cannot use it.
- The page's Content Security Policy forbids any connection except to the app itself. No fonts, scripts or analytics load from anywhere else.
- Uploads and results live in a temporary folder (`hyperocr-…` in your system's temp folder):
  - your original files and the page previews are deleted as soon as a conversion ends;
  - the results are deleted when you click **Convert Other Files**, one hour after the conversion ended if you don't, and when you stop the app (Ctrl+C, or closing its window);
  - if the app is killed instead (a crash, a forced shutdown), its next start deletes what it left. A second copy of the app that is still running keeps its files.
- The only connection HYPER-OCR ever makes is **Software Update**, to `api.github.com` (and GitHub's download server), and only when you click it. It sends no information about you or your files.
- No AI service is called.
- While it converts, HYPER-OCR refuses every outgoing network connection except to this computer itself. Libraries that can report usage are switched off.
- MarkItDown is installed without its file-type guesser, `magika`. That guesser runs on ONNX Runtime, which contacts Microsoft's telemetry servers as soon as it is loaded. HYPER-OCR always gives MarkItDown HTML, so it doesn't need the guesser, and it blocks ONNX Runtime from loading at all.

## How it works

1. Pictures are first placed on PDF pages, one picture per page (JPEGs are kept byte for byte). Each page is then rendered to an image (300 dpi by default), and Tesseract's orientation detection checks which way up it is: an upside-down or sideways page is turned upright by its display rotation (the scan itself isn't changed), and the results screen lists the pages it turned.
2. **Unlimited-OCR** (experimental, off by default) returns the page as tagged blocks: `<|det|>text [113, 567, 884, 698]<|/det|>…`. Each block has a type (title, text, table, image, caption, formula…) and a box on a 0–1000 grid. Tables come back as HTML. The model doesn't report individual lines, so HYPER-OCR finds each block's text lines in the image and spreads the block's words over them.
3. **Tesseract** reads words with their exact positions. First, HYPER-OCR removes scanner specks with a median filter; specks otherwise turn into fake Arabic dots. Then:
   - it finds bordered tables from their ruling lines, merged cells included, and reads each cell separately;
   - it finds figures as large areas of ink that aren't text;
   - it spots headings by letter size and stroke weight, and captions by "Figure 2." / "Table 1." / "شكل" / "جدول";
   - when several languages are ticked, it reads uncertain words with each language alone and keeps the most confident reading. This fixes Arabic words that a mixed model misreads as Latin look-alikes.
4. **Searchable PDF**: the text is written in invisible ink with a "glyphless" font, the method Tesseract and OCRmyPDF use. The original page images are never re-compressed. Arabic is stored in visual order, like born-digital PDFs. Search was tested in:
   - Chrome and Edge (PDFium);
   - Firefox (pdf.js);
   - MuPDF-based readers;
   - Poppler-based readers.

   Born-digital pages (typed text covering the page) keep their own text and are listed in a note on the results screen. A scan with a little real text on it, such as a fax header or a digital stamp, is still a scan: it gets a full OCR layer and keeps the stamp. An old OCR layer is replaced, not doubled.
5. **Images** are cut out at the scan's own resolution (up to 600 dpi). **Tables** become Word files.
6. **Markdown**: the blocks are assembled into an HTML document in reading order, and Microsoft MarkItDown converts it to Markdown. Formulas come out as `$…$` and `$$…$$` LaTeX.

## Limits

- **Tesseract** finds tables that have **visible borders**. Borderless tables come out as text.
- Handwriting, stamps and very poor scans read badly with Tesseract.
- At *Fast · 200 dpi*, small digits and decimal points can be misread (a lab range "1.2-0.6" came out as "1.2-06" in testing). Keep 300 dpi or more for documents where numbers matter.
- In Arabic text, searching for a single word works in every viewer. Searching a phrase that mixes Arabic with numbers or English may not, in any viewer; born-digital Arabic PDFs behave the same way.
- The experimental Unlimited-OCR path (off by default) was never run on a real GPU; it was tested only with simulated model output.

## Troubleshooting

| Message or problem | What to do |
|---|---|
| "Tesseract isn't installed" | Run the setup again. On Windows you can also install it from <https://github.com/UB-Mannheim/tesseract/wiki>. |
| "This PDF is password-protected" | Open it, save a copy without the password, and convert the copy. |
| A language is missing from the list | `python -m hyperocr.languages add <code>` (see [Languages](#languages)), then restart. |
| The browser didn't open | Open <http://127.0.0.1:8765> yourself. If that port was taken, the black window shows the address it used. |
| Out of memory on a huge PDF | Choose *Fast · 200 dpi*, or split the PDF. |
| An iPhone photo shows a plain icon instead of a preview | Normal: most browsers can't show HEIC. HYPER-OCR still reads it. |
| "Couldn't reach GitHub" when updating | Check the internet connection and try again. Nothing was changed. |
| An update failed | The previous version was restored from `.backup/`. Try again, or run `update-windows.bat` / `./update.sh` to see the details. |
| The page didn't come back after an update | Close the black window and start the app again. |

## For developers

```
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pip install --no-deps "markitdown>=0.1.2,<0.2"     # without magika / onnxruntime, as setup does
.venv/bin/python -m pytest          # 55 tests; the CPU tests need Tesseract with eng + ara
.venv/bin/python tests/fixtures/make_fixtures.py   # rebuild the scanned test PDFs
```

```
hyperocr/
  __main__.py          supervisor: starts the local server, restarts it after an update
  server.py, jobs.py   JSON API on 127.0.0.1, one worker thread, clean-up
  inputs.py            uploads: PDFs and pictures (HEIC, EXIF orientation), combined or one by one
  pipeline.py          one conversion, start to finish
  update.py            the updater (the only code that goes online, run as its own process)
  document.py          the page model every engine fills in
  engines/
    unlimited.py       Unlimited-OCR (transformers on CUDA, or a local vLLM/SGLang server)
    detparse.py        parser for Unlimited-OCR's tagged output
    tesseract_engine.py, layout_cv.py   Tesseract plus OpenCV layout analysis
  outputs/
    textlayer.py       invisible searchable text (glyphless font, bidi-aware)
    images.py, tables.py, tablegrid.py, markdown.py
  static/              the interface (no external resources)
    style.css          Apple-style tokens and components, light and dark
    motion.js          springs (damping + response), momentum projection, rubber-banding
    app.js, i18n.js    the page, English and Arabic
design-system-apple/   the "Apple style App" design system: project/ (published to Claude Design), build.py
design-system/         the original "Attendance Register" design system (version 1.0's look)
```

Since version 1.1 the interface uses Apple's system colours, type scale and components, in `hyperocr/static/style.css`. Every colour is a token with a light and a dark value, secondary text uses Apple's higher-contrast greys so it passes WCAG AA, and the page honours *Reduce Motion*, *Reduce Transparency* and *Increase Contrast*. Animations are springs that start from where things are now, so you can interrupt any of them: a dragged row, a sheet you pull down, the segmented control.

The same look is published in Claude Design as the **Apple style App** design system (tokens for both themes, 19 components with live previews, icons, motion rules). Its files are in `design-system-apple/project/`. After any change to the interface, run `python design-system-apple/build.py` to sync it (a test fails until you do), then republish the changed files; `CLAUDE.md` has the steps.

`design-system/` keeps the green **Attendance Register** design system that version 1.0 used. It is still published in Claude Design; `python design-system/build_css.py` writes its CSS to `design-system/build/`.

## Credits and licences

- [Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) by Baidu (MIT)
- [MarkItDown](https://github.com/microsoft/markitdown) by Microsoft (MIT)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (Apache 2.0); HYPER-OCR also bundles Tesseract's 572-byte glyphless font, `hyperocr/outputs/glyphless.ttf`, under the same licence
- [pi-heif](https://pypi.org/project/pi-heif/) for iPhone photos: the decode-only edition of pillow-heif (BSD-3-Clause), bundling [libheif](https://github.com/strukturag/libheif) and [libde265](https://github.com/strukturag/libde265) (LGPL-3.0)

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for every library and its licence. Note that PyMuPDF is AGPL-3.0, which matters if you ever distribute HYPER-OCR or run it as a service for others.

**iPhone photos (HEIC).** All the software HYPER-OCR uses to read them is free and open source; there is nothing to pay. HEIC pictures are compressed with HEVC (H.265), a video format covered by patents that are licensed through patent pools ([Access Advance](https://accessadvance.com/), [Via LA](https://www.via-la.com/licensing-programs/hevc-vvc/)). Those licences are taken by companies that sell devices or software with HEVC built in, and are paid per unit sold. Using HYPER-OCR yourself, or inside your organisation, involves no sale. If you plan to sell or distribute HYPER-OCR, get legal advice on HEVC first, or remove HEIC support by uninstalling `pi-heif`; every other format keeps working.
