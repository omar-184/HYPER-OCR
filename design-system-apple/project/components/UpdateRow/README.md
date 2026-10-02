# UpdateRow

The Software Update row in the About sheet, with its button and, while updating, a list of steps.

**Use** once, in About. The page provides the status line under the title and, while updating, one step per stage ("Downloading 1.1.1…", "Installing…", "Restarting…").

- Idle and up to date: a tinted **Check** button. Update available: the button turns filled and reads **Update**. Failed: the status line in `red-text` and **Try Again**.
- Steps: the current one shows a spinner (a conic `label-2` ring turning every .9s) in `label`; finished ones a `check` in `green-text`. Steps line up with the row label (56px in).
- The button waits while a conversion is running; the status explains why.
- The footer under the group says what an update replaces. The browser version keeps Python, Tesseract and the languages; the desktop app (when `/api/system` reports `desktop`) installs the whole new version and reopens, so its footer says so ("…installs it over this one: HYPER-OCR closes and opens again."). The steps are the same; the desktop app's window closes at "Restarting".
