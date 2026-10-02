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
| [pillow-heif](https://github.com/bigcat88/pillow_heif) | reading iPhone photos (HEIC/HEIF) | BSD-3-Clause source; binary wheels GPL-2.0 because they bundle [libheif](https://github.com/strukturag/libheif) and [libde265](https://github.com/strukturag/libde265) (LGPL-3.0) and [x265](https://bitbucket.org/multicoreware/x265_git) (GPL-2.0) |
| [transformers](https://github.com/huggingface/transformers), [PyTorch](https://pytorch.org) (GPU option) | running Unlimited-OCR | Apache 2.0 / BSD-3-Clause |
