# Install and use the desktop app as a person would, and keep a screenshot of every step.
#
#   pwsh tools/demo-windows.ps1 -Setup dist\HYPER-OCR-Setup-1.2.0.exe -Scan tests\fixtures\scanned_english.pdf -Out shots
#
# Run by .github/workflows/demo.yml on a GitHub Windows machine, where nobody can click: buttons
# are found by reading the screen with Tesseract (the build's own, in dist\HYPER-OCR) and clicked.
param(
  [Parameter(Mandatory)] [string] $Setup,
  [Parameter(Mandatory)] [string] $Scan,
  [Parameter(Mandatory)] [string] $Out,
  [string] $Tesseract = "dist\HYPER-OCR\tesseract\tesseract.exe",
  [string] $Tessdata = "dist\HYPER-OCR\tessdata"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class Mouse {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  public static void Click(int x, int y) {
    SetCursorPos(x, y); mouse_event(2, 0, 0, 0, UIntPtr.Zero); mouse_event(4, 0, 0, 0, UIntPtr.Zero);
  }
}
"@
New-Item -ItemType Directory -Force $Out | Out-Null
$Scan = (Resolve-Path $Scan).Path
$shell = New-Object -ComObject WScript.Shell
$script:step = 0

function Shot([string] $name) {
  $script:step++
  $file = Join-Path $Out ("{0:d2}-{1}" -f $script:step, $name)
  $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
  $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
  $bmp.Save("$file.png")
  $small = New-Object System.Drawing.Bitmap $bmp, ([int]($b.Width * 0.6)), ([int]($b.Height * 0.6))
  $small.Save("$file.jpg", [System.Drawing.Imaging.ImageFormat]::Jpeg)
  $small.Dispose(); $g.Dispose(); $bmp.Dispose()
  Write-Host "screenshot $($script:step): $name"
  return "$file.png"
}

function Find-Word([string] $png, [string[]] $words) {
  # The centre of the first of $words that Tesseract reads on the screenshot, or $null.
  $tsv = & $Tesseract $png stdout --tessdata-dir $Tessdata -l eng --psm 11 tsv 2>$null
  foreach ($word in $words) {
    foreach ($line in $tsv | Select-Object -Skip 1) {
      $f = $line -split "`t"
      if ($f.Count -ge 12 -and $f[11].Trim() -eq $word) {
        return @{ word = $word; x = [int]$f[6] + [int]([int]$f[8] / 2); y = [int]$f[7] + [int]([int]$f[9] / 2) }
      }
    }
  }
  return $null
}

function Click-Word([string] $png, [string[]] $words) {
  $hit = Find-Word $png $words
  if ($hit) { Write-Host "click '$($hit.word)' at $($hit.x),$($hit.y)"; [Mouse]::Click($hit.x, $hit.y) }
  return $hit
}

# ---- 1. The installer, page by page
$setupProcess = Start-Process (Resolve-Path $Setup).Path -PassThru
Start-Sleep 5
foreach ($i in 1..12) {
  if ($setupProcess.HasExited) { break }
  $shot = Shot "installer"
  $hit = Click-Word $shot @("OK", "Next", "Install", "Finish")
  if (-not $hit) { Write-Host "  (no button to click yet: installing)" }
  Start-Sleep 4
}
if (-not $setupProcess.HasExited) { throw "the installer did not finish" }
"installer exit code: $($setupProcess.ExitCode)"

# ---- 2. HYPER-OCR opens by itself at the end
$log = "$env:LOCALAPPDATA\HYPER-OCR\hyperocr.log"
foreach ($i in 1..90) {
  if (Select-String -Path $log -Pattern "The window shows the interface" -Quiet -ErrorAction SilentlyContinue) { break }
  Start-Sleep 1
}
Start-Sleep 3
$shot = Shot "app-opened"

# ---- 3. Choose a scan through the window
if (-not (Click-Word $shot @("Choose", "PDFs"))) { throw "no 'Choose PDFs or Photos' on screen" }
Start-Sleep 4
Shot "file-dialog" | Out-Null
[System.Windows.Forms.SendKeys]::SendWait($Scan)
Start-Sleep 1
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep 4
Shot "file-chosen" | Out-Null

# ---- 4. Convert it: the button is further down the page
[System.Windows.Forms.SendKeys]::SendWait("{END}")
Start-Sleep 2
$shot = Shot "scrolled-to-convert"
if (-not (Click-Word $shot @("Convert"))) { throw "no 'Convert' button on screen" }
Start-Sleep 3
Shot "converting" | Out-Null
Start-Sleep 30
Shot "done" | Out-Null
[System.Windows.Forms.SendKeys]::SendWait("{END}")
Start-Sleep 2
Shot "done-scrolled" | Out-Null

"--- the app's log ---"
Get-Content $log -ErrorAction SilentlyContinue
