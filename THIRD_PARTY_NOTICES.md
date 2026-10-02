# Third-party notices

HYPER-OCR uses these projects. Each keeps its own licence.

| Project | Used for | Licence |
|---|---|---|
| [Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) (Baidu) | GPU text and layout recognition (model downloaded by the user) | MIT |
| [MarkItDown](https://github.com/microsoft/markitdown) (Microsoft) | HTML to Markdown conversion | MIT |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | CPU text recognition (installed separately) | Apache 2.0 |
| Tesseract `pdf.ttf` glyphless font, bundled as `hyperocr/outputs/glyphless.ttf` | invisible text layer | Apache 2.0, © Google Inc. |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) / MuPDF | reading, rendering and writing PDFs | AGPL-3.0 (commercial licences available from Artifex) |
| [OpenCV](https://opencv.org) | table and figure detection | Apache 2.0 |
| [python-docx](https://github.com/python-openxml/python-docx) | Word tables | MIT |
| [python-bidi](https://github.com/MeirKriheli/python-bidi) | right-to-left ordering in the text layer | LGPL-3.0 |
| [pytesseract](https://github.com/madmaze/pytesseract) | calling Tesseract | Apache 2.0 |
| [Flask](https://flask.palletsprojects.com) / [Waitress](https://github.com/Pylons/waitress) | the local web server | BSD-3-Clause / ZPL 2.1 |
| [NumPy](https://numpy.org), [Pillow](https://python-pillow.org) | image handling | BSD / MIT-CMU |
| [pi-heif](https://pypi.org/project/pi-heif/) (decode-only edition of [pillow-heif](https://github.com/bigcat88/pillow_heif)) | reading iPhone photos (HEIC/HEIF) | BSD-3-Clause; its wheels bundle [libheif](https://github.com/strukturag/libheif) and [libde265](https://github.com/strukturag/libde265), LGPL-3.0 (no HEVC encoder). HEVC itself is patent-licensed through pools such as Access Advance and Via LA; see the README. |
| [transformers](https://github.com/huggingface/transformers), [PyTorch](https://pytorch.org) (GPU option) | running Unlimited-OCR | Apache 2.0 / BSD-3-Clause |

## The desktop app (Windows installer)

`HYPER-OCR-Setup-<version>.exe` also carries these. (Of UB Mannheim's Tesseract build it takes only the program and the libraries it loads, not the training tools or theirs.) Their licence texts are in the app's folder (`tesseract\doc\` for Tesseract) or at the links; the source of every one of them is public at the link.

| Project | Used for | Licence |
|---|---|---|
| [Python](https://www.python.org) 3.12 | runs the app | PSF License |
| [pywebview](https://github.com/r0x0r/pywebview), [pythonnet](https://github.com/pythonnet/pythonnet), clr-loader | the app's window | BSD-3-Clause, MIT, MIT |
| Microsoft WebView2 SDK libraries (bundled with pywebview); the WebView2 Runtime itself is part of Windows | showing the interface | Microsoft's WebView2 SDK licence (redistributable) |
| [PyInstaller](https://pyinstaller.org) bootloader | starting the bundled Python | GPL-2.0 with an exception that allows bundling any program |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | the installer and uninstaller | Inno Setup License (free, including commercial use) |
| Tesseract 5.4.0, [UB Mannheim's Windows build](https://github.com/UB-Mannheim/tesseract) | text recognition | Apache 2.0 |
| Tesseract's [language files](https://github.com/tesseract-ocr/tessdata) `eng`, `ara`, `osd` | English, Arabic, page orientation | Apache 2.0 |
| The libraries Tesseract loads, from UB Mannheim's build ([MSYS2 / mingw-w64 packages](https://github.com/msys2/MINGW-packages)): Leptonica, libarchive, libtiff, libpng, libjpeg-turbo, libwebp, OpenJPEG, giflib, LERC, zlib, zstd, lz4, xz, bzip2, libdeflate, libb2, expat, OpenSSL (libcrypto) | reading images and archives for Tesseract | permissive licences (BSD, MIT, zlib, libpng, libtiff, IJG, Apache 2.0) |
| … from the same build: GNU libiconv | character-set conversion | LGPL-2.1 or later; a separate DLL you may replace |
| … from the same build: JBIG-KIT (libjbig) | JBIG images in TIFF files | GPL-2.0 or later, compatible with HYPER-OCR's AGPL-3.0 |
| … from the same build: the GCC runtime (libgcc, libstdc++), winpthreads | C and C++ runtime | GPL-3.0 with the GCC Runtime Library Exception; MIT/BSD |

This summary is for orientation, not legal advice. Before selling or redistributing HYPER-OCR in a product, have the licences reviewed.
