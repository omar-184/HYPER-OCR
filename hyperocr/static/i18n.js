/* Interface text in English and Arabic. */
(function (H) {
  'use strict';

  const S = {
    title: { en: 'HYPER-OCR', ar: 'HYPER-OCR' },
    subtitle: {
      en: 'Turn scanned PDFs and photos of pages into a searchable PDF, a Markdown file, and their pictures and tables. Works fully offline: your files never leave this computer.',
      ar: 'حوّل ملفات PDF الممسوحة وصور الصفحات إلى PDF قابل للبحث وملف Markdown، مع استخراج الصور والجداول. يعمل دون إنترنت: لا تغادر ملفاتك هذا الجهاز.',
    },
    langName: { en: 'العربية', ar: 'English' },
    langBtn: { en: 'Switch to Arabic', ar: 'التبديل إلى الإنجليزية' },
    theme_auto: { en: 'Automatic', ar: 'تلقائي' },
    theme_dark: { en: 'Dark', ar: 'داكن' },
    theme_light: { en: 'Light', ar: 'فاتح' },
    themeBtn: { en: 'Appearance: {mode}', ar: 'المظهر: {mode}' },
    aboutBtn: { en: 'About and updates', ar: 'حول التطبيق والتحديثات' },

    filesHeader: { en: 'Files', ar: 'الملفات' },
    dropTitle: { en: 'Choose PDFs or Photos', ar: 'اختر ملفات PDF أو صوراً' },
    dropSub: { en: 'or drop them here', ar: 'أو اسحبها إلى هنا' },
    filesFooter: {
      en: 'PDF, JPG, PNG, HEIC (iPhone), TIFF, WebP and BMP. Add several to combine them or convert each one on its own.',
      ar: 'PDF وJPG وPNG وHEIC (آيفون) وTIFF وWebP وBMP. أضف عدة ملفات لدمجها أو لتحويل كل منها على حدة.',
    },
    addMore: { en: 'Add More Files', ar: 'إضافة ملفات أخرى' },
    kindPdf: { en: 'PDF', ar: 'PDF' },
    kindImage: { en: 'Photo', ar: 'صورة' },
    remove: { en: 'Remove {name}', ar: 'إزالة {name}' },
    reorder: { en: 'Reorder {name}. Use the up and down arrow keys.', ar: 'إعادة ترتيب {name}. استخدم مفتاحي الأسهم للأعلى والأسفل.' },
    moved: { en: '{name} moved to position {n}', ar: 'نُقل {name} إلى الموضع {n}' },
    modeCombine: { en: 'Combine into One', ar: 'دمج في ملف واحد' },
    modeSeparate: { en: 'Each Separately', ar: 'كل ملف على حدة' },
    modeLabel: { en: 'How to convert several files', ar: 'طريقة تحويل عدة ملفات' },
    modeCombineHint: {
      en: 'One searchable PDF with every page, in the order above. Drag the handles to reorder.',
      ar: 'ملف PDF واحد قابل للبحث يضم كل الصفحات بالترتيب أعلاه. اسحب المقابض لإعادة الترتيب.',
    },
    modeSeparateHint: {
      en: 'A searchable PDF, Markdown file, pictures and tables for each file, all in one ZIP.',
      ar: 'ملف PDF قابل للبحث وملف Markdown وصور وجداول لكل ملف، وكلها في ملف ZIP واحد.',
    },
    fileNotSupported: { en: '“{name}” isn’t a PDF or a picture. Choose PDF, JPG, PNG, HEIC, TIFF, WebP or BMP files.', ar: '«{name}» ليس ملف PDF أو صورة. اختر ملفات PDF أو JPG أو PNG أو HEIC أو TIFF أو WebP أو BMP.' },

    recogHeader: { en: 'Text Recognition', ar: 'التعرّف على النص' },
    setEngine: { en: 'Engine', ar: 'المحرك' },
    engAuto: { en: 'Automatic', ar: 'تلقائي' },
    engGpu: { en: 'Unlimited-OCR (GPU)', ar: 'Unlimited-OCR (GPU)' },
    engServer: { en: 'Unlimited-OCR (server)', ar: 'Unlimited-OCR (خادم)' },
    engCpu: { en: 'Tesseract', ar: 'Tesseract' },
    engUnavailable: { en: '{name}: not available', ar: '{name}: غير متاح' },
    setDpi: { en: 'Resolution', ar: 'الدقة' },
    dpi300: { en: 'Standard', ar: 'عادية' },
    dpi200: { en: 'Fast', ar: 'سريعة' },
    dpi400: { en: 'Small Print', ar: 'للخط الصغير' },
    setLangs: { en: 'Languages', ar: 'اللغات' },
    setLangsHint: {
      en: 'Tesseract reads only the languages ticked here. Unlimited-OCR recognises the language by itself.',
      ar: 'يقرأ Tesseract اللغات المحددة هنا فقط، أما Unlimited-OCR فيتعرّف على اللغة تلقائياً.',
    },
    noLangs: { en: 'None installed', ar: 'غير مثبتة' },
    langsMore: { en: '{first} + {n} more', ar: '{first} و{n} أخرى' },

    st_gpuReady: { en: 'Unlimited-OCR will read the pages on this computer’s NVIDIA GPU ({detail}).', ar: 'سيقرأ Unlimited-OCR الصفحات باستخدام بطاقة NVIDIA في هذا الجهاز ({detail}).' },
    st_serverReady: { en: 'Unlimited-OCR will read the pages through the local server at {detail}.', ar: 'سيقرأ Unlimited-OCR الصفحات عبر الخادم المحلي على {detail}.' },
    st_cpu: { en: 'Tesseract will read the pages on this computer’s processor.', ar: 'سيقرأ Tesseract الصفحات باستخدام معالج هذا الجهاز.' },
    st_noNvidiaGpu: {
      en: 'No NVIDIA graphics card found, so Tesseract will read the pages. Unlimited-OCR needs an NVIDIA GPU.',
      ar: 'لم يتم العثور على بطاقة NVIDIA، لذلك سيقرأ Tesseract الصفحات. يحتاج Unlimited-OCR إلى بطاقة NVIDIA.',
    },
    st_gpuPackagesMissing: {
      en: 'Tesseract will read the pages. To use Unlimited-OCR on an NVIDIA GPU, run the setup again and choose the GPU option.',
      ar: 'سيقرأ Tesseract الصفحات. لاستخدام Unlimited-OCR على بطاقة NVIDIA شغّل الإعداد مرة أخرى واختر خيار GPU.',
    },
    st_modelMissing: {
      en: 'NVIDIA GPU found ({detail}), but the Unlimited-OCR model isn’t downloaded yet. Run “download-model” once, then restart. Until then Tesseract reads the pages.',
      ar: 'تم العثور على بطاقة NVIDIA ‏({detail}) لكن نموذج Unlimited-OCR لم يُنزَّل بعد. شغّل «download-model» مرة واحدة ثم أعد التشغيل. حتى ذلك الحين يقرأ Tesseract الصفحات.',
    },
    st_checking: { en: 'Checking this computer…', ar: 'جارٍ فحص هذا الجهاز…' },

    outputHeader: { en: 'Output', ar: 'الملفات الناتجة' },
    optFurniture: { en: 'Leave page headers, footers and numbers out of the Markdown', ar: 'استبعاد ترويسة الصفحة وتذييلها وأرقامها من ملف Markdown' },
    outputFooter: {
      en: 'You get one ZIP: a searchable PDF, a Markdown file, an Images folder and a Tables folder with one Word file per table, each with a picture of the original table to check the numbers against.',
      ar: 'تحصل على ملف ZIP واحد: PDF قابل للبحث وملف Markdown ومجلد Images للصور ومجلد Tables فيه ملف Word لكل جدول، مع صورة الجدول الأصلي لمطابقة الأرقام عليها.',
    },
    start: { en: 'Convert', ar: 'تحويل' },
    startHint: { en: 'Choose a file first.', ar: 'اختر ملفاً أولاً.' },

    cancel: { en: 'Cancel', ar: 'إلغاء' },
    stage_uploading: { en: 'Preparing your files', ar: 'تجهيز الملفات' },
    stage_queued: { en: 'Waiting to start', ar: 'بانتظار البدء' },
    stage_opening: { en: 'Opening the files', ar: 'فتح الملفات' },
    'stage_loading-model': { en: 'Loading Unlimited-OCR', ar: 'تحميل Unlimited-OCR' },
    stage_reading: { en: 'Reading page {page} of {pages}', ar: 'قراءة الصفحة {page} من {pages}' },
    'stage_writing-pdf': { en: 'Writing the searchable PDF', ar: 'كتابة ملف PDF القابل للبحث' },
    'stage_writing-markdown': { en: 'Writing the Markdown file', ar: 'كتابة ملف Markdown' },
    stage_packing: { en: 'Packing the ZIP file', ar: 'تجميع ملف ZIP' },
    stage_done: { en: 'Done', ar: 'تم' },
    docOf: { en: '{name} · file {doc} of {docs}', ar: '{name} · الملف {doc} من {docs}' },
    firstRun: { en: 'The first run takes longer', ar: 'التشغيل الأول يستغرق وقتاً أطول' },
    etaSeconds: { en: 'About {n}\u00a0s left', ar: 'بقي نحو {n}\u00a0ث' },
    etaMinutes: { en: 'About {n}\u00a0min left', ar: 'بقي نحو {n}\u00a0د' },
    percent: { en: '{n}%', ar: '{n}٪' },

    err_notPdf: { en: '“{detail}” couldn’t be opened as a PDF.', ar: 'تعذر فتح «{detail}» كملف PDF.' },
    err_notSupported: { en: '“{detail}” isn’t a PDF or a picture this app can read.', ar: '«{detail}» ليس ملف PDF أو صورة يمكن قراءتها.' },
    err_badImage: { en: 'The picture “{detail}” couldn’t be read. It may be damaged.', ar: 'تعذرت قراءة الصورة «{detail}». ربما تكون تالفة.' },
    err_passwordProtected: { en: '“{detail}” is password-protected. Open it, save a copy without the password, and choose the copy.', ar: '«{detail}» محمي بكلمة مرور. افتحه واحفظ نسخة بدونها ثم اختر النسخة.' },
    err_emptyPdf: { en: '“{detail}” has no pages.', ar: 'لا يحتوي «{detail}» على صفحات.' },
    err_tooBig: { en: 'These files add up to more than 2 GB. Convert them in smaller groups.', ar: 'حجم الملفات أكبر من 2 غيغابايت. حوّلها على دفعات أصغر.' },
    err_tooManyFiles: { en: 'Choose at most {detail} files at a time.', ar: 'اختر {detail} ملفاً على الأكثر في كل مرة.' },
    err_noFile: { en: 'Choose a file first.', ar: 'اختر ملفاً أولاً.' },
    err_tesseractMissing: { en: 'Tesseract isn’t installed. Run the setup again, then restart the app.', ar: 'برنامج Tesseract غير مثبت. شغّل الإعداد مرة أخرى ثم أعد تشغيل التطبيق.' },
    err_noNvidiaGpu: { en: 'Unlimited-OCR needs an NVIDIA GPU and none was found. Choose Automatic or Tesseract.', ar: 'يحتاج Unlimited-OCR إلى بطاقة NVIDIA ولم يُعثر على واحدة. اختر «تلقائي» أو Tesseract.' },
    err_gpuPackagesMissing: { en: 'The GPU add-on isn’t installed. Run the setup again with the GPU option, or choose Tesseract.', ar: 'إضافة GPU غير مثبتة. شغّل الإعداد مرة أخرى مع خيار GPU أو اختر Tesseract.' },
    err_modelMissing: { en: 'The Unlimited-OCR model isn’t downloaded. Run “download-model” once, then restart.', ar: 'نموذج Unlimited-OCR غير منزَّل. شغّل «download-model» مرة واحدة ثم أعد التشغيل.' },
    err_modelLoadFailed: { en: 'Unlimited-OCR couldn’t be loaded ({detail}). Choose Tesseract, or download the model again.', ar: 'تعذر تحميل Unlimited-OCR ‏({detail}). اختر Tesseract أو نزّل النموذج مرة أخرى.' },
    err_ocrFailed: { en: 'Text recognition stopped with an error ({detail}). Try again, or choose Tesseract.', ar: 'توقف التعرّف على النص بسبب خطأ ({detail}). حاول مرة أخرى أو اختر Tesseract.' },
    err_serverUnreachable: { en: 'The local Unlimited-OCR server isn’t answering. Start it, or choose another engine.', ar: 'الخادم المحلي لـ Unlimited-OCR لا يستجيب. شغّله أو اختر محركاً آخر.' },
    err_outOfMemory: { en: 'This computer ran out of memory. Choose the Fast resolution, or convert fewer pages at a time.', ar: 'نفدت ذاكرة هذا الجهاز. اختر الدقة السريعة أو حوّل صفحات أقل في كل مرة.' },
    err_jobLost: {
      en: 'This conversion is no longer on this computer: HYPER-OCR was restarted, or its results were more than an hour old. Convert the files again.',
      ar: 'لم يعد هذا التحويل موجوداً على هذا الجهاز: أُعيد تشغيل HYPER-OCR أو مضت على نتائجه أكثر من ساعة. حوّل الملفات مرة أخرى.',
    },
    err_unexpected: { en: 'Something went wrong: {detail}', ar: 'حدث خطأ: {detail}' },
    err_network: { en: 'HYPER-OCR stopped responding. Make sure its window is still open, then try again.', ar: 'توقف HYPER-OCR عن الاستجابة. تأكد أن نافذته ما زالت مفتوحة ثم حاول مرة أخرى.' },

    doneTitle: { en: 'Done', ar: 'اكتمل التحويل' },
    numbersWarningTitle: { en: 'Every number HYPER-OCR reads is unverified.', ar: 'كل رقم يقرؤه HYPER-OCR غير مُتحقَّق منه.' },
    numbersWarning: {
      en: 'Check each one against the original before you use it, including text copied from the searchable PDF. Each Word table has a picture of the original table for this.',
      ar: 'طابِق كل رقم مع الأصل قبل استخدامه، بما في ذلك النص المنسوخ من ملف PDF القابل للبحث. يحتوي كل ملف Word لجدول على صورة الجدول الأصلي لهذا الغرض.',
    },
    doneSub: { en: '{files} · read by {engine} in {time}', ar: '{files} · بواسطة {engine} خلال {time}' },
    seconds: { en: '{n}\u00a0s', ar: '{n}\u00a0ث' },
    minutes: { en: '{m}\u00a0min {s}\u00a0s', ar: '{m}\u00a0د {s}\u00a0ث' },
    statPages: { en: 'Pages', ar: 'صفحات' },
    statWords: { en: 'Words', ar: 'كلمات' },
    statImages: { en: 'Pictures', ar: 'صور' },
    statTables: { en: 'Tables', ar: 'جداول' },
    dlZip: { en: 'Download All (ZIP)', ar: 'تنزيل الكل (ZIP)' },
    dlZipShort: { en: 'Download All', ar: 'تنزيل الكل' },
    pdfRow: { en: 'Searchable PDF', ar: 'PDF قابل للبحث' },
    mdRow: { en: 'Markdown', ar: 'Markdown' },
    download: { en: 'Download {name}', ar: 'تنزيل {name}' },
    resImages: { en: 'Pictures and Figures', ar: 'الصور والأشكال' },
    resTables: { en: 'Tables', ar: 'الجداول' },
    resMarkdown: { en: 'Markdown Preview', ar: 'معاينة Markdown' },
    noImages: { en: 'No pictures or figures were found.', ar: 'لم يتم العثور على صور أو أشكال.' },
    noTables: { en: 'No tables were found.', ar: 'لم يتم العثور على جداول.' },
    tableName: { en: 'Table {n}', ar: 'جدول {n}' },
    tableMeta: { en: 'Page {page} · {rows} × {cols}', ar: 'الصفحة {page} · {rows} × {cols}' },
    mdTruncated: { en: 'Only the beginning is shown. The whole file is in the ZIP.', ar: 'يظهر الجزء الأول فقط. الملف الكامل موجود في ملف ZIP.' },
    again: { en: 'Convert Other Files', ar: 'تحويل ملفات أخرى' },
    w_usedCpu: { en: 'Tesseract read these files because Unlimited-OCR isn’t available on this computer.', ar: 'قرأ Tesseract هذه الملفات لأن Unlimited-OCR غير متاح على هذا الجهاز.' },
    // Page notes: `_one` is used for a single page. The document's name, when there are several, goes before them.
    w_turned_one: { en: 'Page {pages} was upside down or sideways, so it was turned upright.', ar: 'كانت الصفحة {pages} مقلوبة أو على جانبها، فأُديرت إلى وضعها الصحيح.' },
    w_turned: { en: 'Pages {pages} were upside down or sideways, so they were turned upright.', ar: 'كانت الصفحات {pages} مقلوبة أو على جوانبها، فأُديرت إلى وضعها الصحيح.' },
    w_keptText_one: { en: 'Page {pages} already had its own text, so it was kept as it is.', ar: 'الصفحة {pages} تحتوي على نص أصلاً، لذلك تُرك كما هو.' },
    w_keptText: { en: 'Pages {pages} already had their own text, so it was kept as it is.', ar: 'الصفحات {pages} تحتوي على نص أصلاً، لذلك تُرك كما هو.' },
    w_noText_one: { en: 'No text was found on page {pages}. If it does have text, try Small Print.', ar: 'لم يُعثر على نص في الصفحة {pages}. إذا كانت تحتوي على نص فجرّب دقة «للخط الصغير».' },
    w_noText: { en: 'No text was found on pages {pages}. If they do have text, try Small Print.', ar: 'لم يُعثر على نص في الصفحات {pages}. إذا كانت تحتوي على نص فجرّب دقة «للخط الصغير».' },

    aboutTitle: { en: 'About', ar: 'حول التطبيق' },
    done: { en: 'Done', ar: 'تم' },
    version: { en: 'Version {v}', ar: 'الإصدار {v}' },
    updTitle: { en: 'Software Update', ar: 'تحديث البرنامج' },
    updCheck: { en: 'Check', ar: 'تحقق' },
    updNow: { en: 'Update', ar: 'تحديث' },
    updRetry: { en: 'Try Again', ar: 'حاول مجدداً' },
    updIdle: { en: 'Checks GitHub for a newer version', ar: 'يتحقق من وجود إصدار أحدث على GitHub' },
    updChecking: { en: 'Checking…', ar: 'جارٍ التحقق…' },
    updUpToDate: { en: 'HYPER-OCR {v} is up to date', ar: 'HYPER-OCR {v} محدّث' },
    updAvailable: { en: 'Version {latest} is available', ar: 'الإصدار {latest} متاح' },
    updBusy: { en: 'Wait for the conversion to finish, then update.', ar: 'انتظر حتى ينتهي التحويل ثم حدّث.' },
    updFailed: { en: 'Couldn’t reach GitHub. Check the internet connection and try again.', ar: 'تعذر الوصول إلى GitHub. تحقق من اتصال الإنترنت وحاول مرة أخرى.' },
    updFailedInstall: { en: 'The update didn’t finish ({detail}). Nothing was changed.', ar: 'لم يكتمل التحديث ({detail}). لم يتغير شيء.' },
    step_downloading: { en: 'Downloading version {v}', ar: 'تنزيل الإصدار {v}' },
    step_installing: { en: 'Installing', ar: 'التثبيت' },
    step_packages: { en: 'Updating packages', ar: 'تحديث الحزم' },
    step_restarting: { en: 'Restarting HYPER-OCR', ar: 'إعادة تشغيل HYPER-OCR' },
    updRestartManual: { en: 'Updated. Close HYPER-OCR and start it again to finish.', ar: 'تم التحديث. أغلق HYPER-OCR وشغّله مرة أخرى لإكمال التحديث.' },
    updFooter: {
      en: 'Updating replaces only the app itself. Python, Tesseract, languages and the Unlimited-OCR model stay installed. This button is the only thing in HYPER-OCR that goes online.',
      ar: 'يستبدل التحديث التطبيق نفسه فقط، وتبقى Python وTesseract واللغات ونموذج Unlimited-OCR مثبتة. هذا الزر هو الشيء الوحيد في HYPER-OCR الذي يتصل بالإنترنت.',
    },
    updFooterDesktop: {
      en: 'Updating downloads the new version from GitHub, checks it and installs it over this one: HYPER-OCR closes and opens again. Added languages stay. This button is the only thing in HYPER-OCR that goes online.',
      ar: 'يُنزّل التحديث الإصدار الجديد من GitHub ويتحقق منه ثم يثبّته مكان هذا الإصدار: يُغلق HYPER-OCR ثم يُفتح من جديد. تبقى اللغات المضافة. هذا الزر هو الشيء الوحيد في HYPER-OCR الذي يتصل بالإنترنت.',
    },
    appearanceHeader: { en: 'Appearance', ar: 'المظهر' },
    computerHeader: { en: 'This Computer', ar: 'هذا الجهاز' },
    eng_unlimited: { en: 'Unlimited-OCR', ar: 'Unlimited-OCR' },
    'eng_unlimited-server': { en: 'Unlimited-OCR server', ar: 'خادم Unlimited-OCR' },
    eng_tesseract: { en: 'Tesseract', ar: 'Tesseract' },
    engReady: { en: 'Ready', ar: 'جاهز' },
    engOff: { en: 'Not Available', ar: 'غير متاح' },
    r_noNvidiaGpu: { en: 'No NVIDIA GPU', ar: 'لا توجد بطاقة NVIDIA' },
    r_gpuPackagesMissing: { en: 'GPU add-on not installed', ar: 'إضافة GPU غير مثبتة' },
    r_modelMissing: { en: 'Model not downloaded', ar: 'النموذج غير منزَّل' },
    r_tesseractMissing: { en: 'Not installed', ar: 'غير مثبت' },
    r_serverUnreachable: { en: 'Server not answering', ar: 'الخادم لا يستجيب' },
    privacyFooter: {
      en: 'HYPER-OCR runs only on this computer. While it runs it refuses every connection to the internet; your files are deleted from its temporary folder when you close it.',
      ar: 'يعمل HYPER-OCR على هذا الجهاز فقط، ويرفض أي اتصال بالإنترنت أثناء عمله، وتُحذف ملفاتك من مجلده المؤقت عند إغلاقه.',
    },
    footer: { en: 'Offline: no internet, no cloud AI, no accounts.', ar: 'دون إنترنت: بلا ذكاء اصطناعي سحابي ولا حسابات.' },
  };

  const LANG_NAMES = {
    eng: ['English', 'الإنجليزية'], ara: ['Arabic', 'العربية'], fra: ['French', 'الفرنسية'], deu: ['German', 'الألمانية'],
    spa: ['Spanish', 'الإسبانية'], ita: ['Italian', 'الإيطالية'], por: ['Portuguese', 'البرتغالية'], rus: ['Russian', 'الروسية'],
    tur: ['Turkish', 'التركية'], fas: ['Persian', 'الفارسية'], urd: ['Urdu', 'الأردية'], heb: ['Hebrew', 'العبرية'],
    hin: ['Hindi', 'الهندية'], ben: ['Bengali', 'البنغالية'], nld: ['Dutch', 'الهولندية'], pol: ['Polish', 'البولندية'],
    ukr: ['Ukrainian', 'الأوكرانية'], ell: ['Greek', 'اليونانية'], swe: ['Swedish', 'السويدية'], ron: ['Romanian', 'الرومانية'],
    ind: ['Indonesian', 'الإندونيسية'], msa: ['Malay', 'الملايوية'], jpn: ['Japanese', 'اليابانية'], kor: ['Korean', 'الكورية'],
    chi_sim: ['Chinese (Simplified)', 'الصينية المبسطة'], chi_tra: ['Chinese (Traditional)', 'الصينية التقليدية'],
    lat: ['Latin', 'اللاتينية'], kur: ['Kurdish', 'الكردية'], pus: ['Pashto', 'البشتوية'], snd: ['Sindhi', 'السندية'],
  };
  const NATIVE = { eng: 'English', ara: 'العربية', fra: 'Français', deu: 'Deutsch', spa: 'Español', ita: 'Italiano', por: 'Português',
    rus: 'Русский', tur: 'Türkçe', fas: 'فارسی', urd: 'اردو', heb: 'עברית', hin: 'हिन्दी', jpn: '日本語', kor: '한국어', chi_sim: '简体中文', chi_tra: '繁體中文' };

  // Counted nouns, chosen with Intl.PluralRules (Arabic has six forms).
  const P = {
    startFiles: { en: { other: 'Convert {n} Files' },
      ar: { two: 'تحويل الملفين', few: 'تحويل {n} ملفات', many: 'تحويل {n} ملفاً', other: 'تحويل {n} ملف' } },
    files: { en: { one: '1 file', other: '{n} files' },
      ar: { one: 'ملف واحد', two: 'ملفان', few: '{n} ملفات', many: '{n} ملفاً', other: '{n} ملف' } },
    pages: { en: { one: '1 page', other: '{n} pages' },
      ar: { zero: 'لا صفحات', one: 'صفحة واحدة', two: 'صفحتان', few: '{n} صفحات', many: '{n} صفحة', other: '{n} صفحة' } },
    pictures: { en: { one: '1 picture', other: '{n} pictures' },
      ar: { zero: 'لا صور', one: 'صورة واحدة', two: 'صورتان', few: '{n} صور', many: '{n} صورة', other: '{n} صورة' } },
    tables: { en: { one: '1 table', other: '{n} tables' },
      ar: { zero: 'لا جداول', one: 'جدول واحد', two: 'جدولان', few: '{n} جداول', many: '{n} جدولاً', other: '{n} جدول' } },
  };

  let lang = 'en';

  function plural(key, n) {
    const forms = P[key][lang] || P[key].en;
    let form = 'other';
    try { form = new Intl.PluralRules(lang).select(n); } catch { form = n === 1 ? 'one' : 'other'; }
    return (forms[form] || forms.other).split('{n}').join(num(n));
  }

  function t(key, vars) {
    const entry = S[key];
    let s = entry ? (entry[lang] || entry.en) : key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split('{' + k + '}').join(String(v));
    return s.replace(/\b(Unlimited|HYPER)-OCR\b/g, '$1\u2011OCR');   // never break a product name at its hyphen
  }

  function langName(code) {
    const n = LANG_NAMES[code];
    return n ? n[lang === 'ar' ? 1 : 0] : code;
  }

  function nativeName(code) { return NATIVE[code] || ''; }

  function setLang(l) {
    lang = l === 'ar' ? 'ar' : 'en';
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  }

  function num(n) {
    try { return new Intl.NumberFormat('en-US').format(n); } catch { return String(n); }   // Western digits in both languages
  }

  H.i18n = { t, plural, setLang, langName, nativeName, num, has: (k) => k in S, get lang() { return lang; } };
})(window.HOCR = window.HOCR || {});
