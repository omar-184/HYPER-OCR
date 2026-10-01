/* Interface text in English and Arabic. */
(function (H) {
  'use strict';

  const S = {
    title: { en: 'HYPER-OCR', ar: 'HYPER-OCR' },
    subtitle: {
      en: 'Turn a scanned PDF into a searchable PDF, a Markdown file, its pictures and its tables as Word files. Works fully offline: your files never leave this computer.',
      ar: 'حوّل ملف PDF ممسوحاً ضوئياً إلى PDF قابل للبحث وملف Markdown، مع استخراج الصور والجداول كملفات Word. يعمل دون إنترنت: لا تغادر ملفاتك هذا الجهاز.',
    },
    theme_auto: { en: 'Auto', ar: 'تلقائي' },
    theme_dark: { en: 'Dark', ar: 'داكن' },
    theme_light: { en: 'Light', ar: 'فاتح' },
    themeBtn: { en: 'Colour theme: {mode} (tap to change)', ar: 'المظهر: {mode} (اضغط للتغيير)' },

    fileTitle: { en: 'Choose a scanned PDF', ar: 'اختر ملف PDF ممسوحاً ضوئياً' },
    filePick: { en: 'Choose or drop a PDF', ar: 'اختر ملف PDF أو اسحبه هنا' },
    fileChange: { en: 'Choose a different PDF', ar: 'اختيار ملف PDF آخر' },
    fileHint: {
      en: 'One PDF of scanned pages: articles, reports, lab results, books. Any size; long files take longer.',
      ar: 'ملف PDF واحد لصفحات ممسوحة ضوئياً: مقالات، تقارير، نتائج تحاليل، كتب. بأي حجم، والملفات الطويلة تستغرق وقتاً أطول.',
    },
    fileMeta: { en: '{pages} pages · {size}', ar: '{pages} صفحة · {size}' },
    fileMetaNoPages: { en: '{size}', ar: '{size}' },
    fileRemove: { en: 'Remove this file', ar: 'إزالة هذا الملف' },
    fileNotPdf: { en: 'This file isn’t a PDF. Please choose a .pdf file.', ar: 'هذا الملف ليس بصيغة PDF. الرجاء اختيار ملف \u200e.pdf.' },

    setTitle: { en: 'OCR settings', ar: 'إعدادات التعرّف على النص' },
    setEngine: { en: 'Text recognition', ar: 'محرك التعرّف على النص' },
    engAuto: { en: 'Automatic (recommended)', ar: 'تلقائي (موصى به)' },
    engGpu: { en: 'Unlimited-OCR · NVIDIA GPU', ar: 'Unlimited-OCR · بطاقة NVIDIA' },
    engServer: { en: 'Unlimited-OCR · local server', ar: 'Unlimited-OCR · خادم محلي' },
    engCpu: { en: 'Tesseract · any computer', ar: 'Tesseract · أي جهاز' },
    engUnavailable: { en: '{name} (not available here)', ar: '{name} (غير متاح هنا)' },
    setDpi: { en: 'Reading resolution', ar: 'دقة القراءة' },
    dpi300: { en: 'Standard · 300 dpi (recommended)', ar: 'عادية · 300 نقطة/إنش (موصى بها)' },
    dpi200: { en: 'Fast · 200 dpi', ar: 'سريعة · 200 نقطة/إنش' },
    dpi400: { en: 'Small print · 400 dpi', ar: 'للخط الصغير · 400 نقطة/إنش' },
    setLangs: { en: 'Languages in the document', ar: 'لغات المستند' },
    setLangsHint: {
      en: 'Used by Tesseract. Tick every language that appears; Unlimited-OCR recognises the language by itself.',
      ar: 'يستخدمها Tesseract. حدّد كل لغة موجودة في المستند؛ أما Unlimited-OCR فيتعرّف على اللغة تلقائياً.',
    },
    noLangs: { en: 'No Tesseract languages are installed.', ar: 'لا توجد لغات Tesseract مثبتة.' },
    optSnapshot: { en: 'Add a picture of the original table to each Word file, for checking', ar: 'إضافة صورة الجدول الأصلي إلى كل ملف Word للتحقق' },
    optFurniture: { en: 'Leave page headers, footers and page numbers out of the Markdown', ar: 'استبعاد ترويسة الصفحة وتذييلها وأرقام الصفحات من ملف Markdown' },
    start: { en: 'Convert', ar: 'ابدأ التحويل' },
    startHint: { en: 'Choose a PDF first.', ar: 'اختر ملف PDF أولاً.' },

    st_gpuReady: { en: 'NVIDIA GPU found ({detail}). Unlimited-OCR will read the pages.', ar: 'تم العثور على بطاقة NVIDIA ({detail}). سيقرأ Unlimited-OCR الصفحات.' },
    st_serverReady: { en: 'Unlimited-OCR server found at {detail}. It will read the pages.', ar: 'تم العثور على خادم Unlimited-OCR على {detail}. سيقرأ الصفحات.' },
    st_cpu: { en: 'Tesseract will read the pages on this computer’s processor.', ar: 'سيقرأ Tesseract الصفحات باستخدام معالج هذا الجهاز.' },
    st_noNvidiaGpu: {
      en: 'No NVIDIA graphics card found, so Tesseract will read the pages on the processor. Unlimited-OCR needs an NVIDIA GPU.',
      ar: 'لم يتم العثور على بطاقة رسومات NVIDIA، لذلك سيقرأ Tesseract الصفحات باستخدام المعالج. يحتاج Unlimited-OCR إلى بطاقة NVIDIA.',
    },
    st_gpuPackagesMissing: {
      en: 'The GPU add-on isn’t installed, so Tesseract will read the pages. To use Unlimited-OCR on an NVIDIA GPU, run the setup again and choose the GPU option.',
      ar: 'إضافة البطاقة الرسومية غير مثبتة، لذلك سيقرأ Tesseract الصفحات. لاستخدام Unlimited-OCR على بطاقة NVIDIA شغّل الإعداد مرة أخرى واختر خيار GPU.',
    },
    st_modelMissing: {
      en: 'NVIDIA GPU found ({detail}), but the Unlimited-OCR model isn’t downloaded yet. Run “download-model” once (it needs the internet one time), then restart. Until then Tesseract reads the pages.',
      ar: 'تم العثور على بطاقة NVIDIA ({detail})، لكن نموذج Unlimited-OCR لم يُنزَّل بعد. شغّل «download-model» مرة واحدة (يحتاج الإنترنت مرة واحدة فقط) ثم أعد التشغيل. حتى ذلك الحين يقرأ Tesseract الصفحات.',
    },
    st_checking: { en: 'Checking this computer’s graphics card…', ar: 'جارٍ فحص بطاقة الرسومات في هذا الجهاز…' },

    progTitle: { en: 'Progress', ar: 'سير العمل' },
    cancel: { en: 'Cancel', ar: 'إلغاء' },
    stage_uploading: { en: 'Preparing the file', ar: 'تجهيز الملف' },
    stage_queued: { en: 'Waiting to start', ar: 'بانتظار البدء' },
    stage_opening: { en: 'Opening the PDF', ar: 'فتح ملف PDF' },
    'stage_loading-model': { en: 'Loading the Unlimited-OCR model', ar: 'تحميل نموذج Unlimited-OCR' },
    stage_reading: { en: 'Reading the pages', ar: 'قراءة الصفحات' },
    'stage_writing-pdf': { en: 'Writing the searchable PDF', ar: 'كتابة ملف PDF القابل للبحث' },
    'stage_writing-markdown': { en: 'Writing the Markdown file', ar: 'كتابة ملف Markdown' },
    stage_packing: { en: 'Packing the ZIP file', ar: 'تجميع ملف ZIP' },
    stage_done: { en: 'Done', ar: 'تم' },
    stage_cancelled: { en: 'Cancelled', ar: 'تم الإلغاء' },
    pageOf: { en: 'Page {page} of {pages}', ar: 'الصفحة {page} من {pages}' },
    percent: { en: '{n}%', ar: '{n}٪' },
    firstRun: { en: 'first run takes longer', ar: 'التشغيل الأول يستغرق وقتاً أطول' },
    withEngine: { en: ' · {engine}', ar: ' · {engine}' },

    err_notPdf: { en: 'This file isn’t a PDF the app can open. Please choose a .pdf file.', ar: 'تعذر فتح هذا الملف كملف PDF. الرجاء اختيار ملف \u200e.pdf.' },
    err_passwordProtected: { en: 'This PDF is password-protected. Remove the password (open it and save a copy without one), then choose it again.', ar: 'ملف PDF هذا محمي بكلمة مرور. أزل كلمة المرور (افتحه واحفظ نسخة بدونها) ثم اختره مرة أخرى.' },
    err_emptyPdf: { en: 'This PDF has no pages.', ar: 'لا يحتوي ملف PDF هذا على صفحات.' },
    err_tooBig: { en: 'This file is larger than 2 GB. Split it into smaller PDFs and convert them one by one.', ar: 'حجم الملف أكبر من 2 غيغابايت. قسّمه إلى ملفات أصغر وحوّلها واحداً تلو الآخر.' },
    err_noFile: { en: 'Choose a PDF first.', ar: 'اختر ملف PDF أولاً.' },
    err_tesseractMissing: { en: 'Tesseract isn’t installed. Run the setup again, or install Tesseract OCR, then restart the app.', ar: 'برنامج Tesseract غير مثبت. شغّل الإعداد مرة أخرى أو ثبّت Tesseract OCR، ثم أعد تشغيل التطبيق.' },
    err_noNvidiaGpu: { en: 'Unlimited-OCR needs an NVIDIA GPU, and none was found. Choose “Automatic” or Tesseract.', ar: 'يحتاج Unlimited-OCR إلى بطاقة NVIDIA ولم يتم العثور على واحدة. اختر «تلقائي» أو Tesseract.' },
    err_gpuPackagesMissing: { en: 'The GPU add-on isn’t installed. Run the setup again with the GPU option, or choose Tesseract.', ar: 'إضافة البطاقة الرسومية غير مثبتة. شغّل الإعداد مرة أخرى مع خيار GPU، أو اختر Tesseract.' },
    err_modelMissing: { en: 'The Unlimited-OCR model isn’t downloaded. Run “download-model” once, then restart.', ar: 'نموذج Unlimited-OCR غير منزَّل. شغّل «download-model» مرة واحدة ثم أعد التشغيل.' },
    err_modelLoadFailed: { en: 'The Unlimited-OCR model couldn’t be loaded ({detail}). Choose Tesseract, or download the model again.', ar: 'تعذر تحميل نموذج Unlimited-OCR \u200f({detail}). اختر Tesseract أو نزّل النموذج مرة أخرى.' },
    err_ocrFailed: { en: 'Text recognition stopped with an error ({detail}). Try again, or choose Tesseract.', ar: 'توقف التعرّف على النص بسبب خطأ ({detail}). حاول مرة أخرى أو اختر Tesseract.' },
    err_serverUnreachable: { en: 'The local Unlimited-OCR server isn’t answering. Start it, or choose another engine.', ar: 'الخادم المحلي لـ Unlimited-OCR لا يستجيب. شغّله أو اختر محركاً آخر.' },
    err_outOfMemory: { en: 'This computer ran out of memory. Choose the Fast resolution, or split the PDF.', ar: 'نفدت ذاكرة هذا الجهاز. اختر الدقة السريعة أو قسّم ملف PDF.' },
    err_unexpected: { en: 'Something went wrong: {detail}', ar: 'حدث خطأ: {detail}' },
    err_network: { en: 'The app stopped responding. Make sure its window is still open, then try again.', ar: 'توقف التطبيق عن الاستجابة. تأكد أن نافذته ما زالت مفتوحة ثم حاول مرة أخرى.' },

    resTitle: { en: 'Your files', ar: 'ملفاتك' },
    statPages: { en: 'pages', ar: 'صفحة' },
    statWords: { en: 'words', ar: 'كلمة' },
    statImages: { en: 'pictures', ar: 'صورة' },
    statTables: { en: 'tables', ar: 'جدول' },
    statSeconds: { en: 'seconds', ar: 'ثانية' },
    dlZip: { en: 'Download everything (ZIP)', ar: 'تنزيل الكل (ZIP)' },
    dlZipShort: { en: 'Download ZIP', ar: 'تنزيل ZIP' },
    dlPdf: { en: 'Searchable PDF', ar: 'PDF قابل للبحث' },
    dlMd: { en: 'Markdown', ar: 'Markdown' },
    dlFile: { en: 'Download', ar: 'تنزيل' },
    again: { en: 'Convert another PDF', ar: 'تحويل ملف PDF آخر' },
    againShort: { en: 'Another PDF', ar: 'ملف آخر' },
    zipHint: {
      en: 'The ZIP holds the searchable PDF, the Markdown file, an “Images” folder and a “Tables” folder with one Word file per table.',
      ar: 'يحتوي ملف ZIP على ملف PDF القابل للبحث وملف Markdown ومجلد «Images» للصور ومجلد «Tables» فيه ملف Word لكل جدول.',
    },
    resImages: { en: 'Pictures and figures', ar: 'الصور والأشكال' },
    resTables: { en: 'Tables', ar: 'الجداول' },
    resMarkdown: { en: 'Markdown', ar: 'ملف Markdown' },
    noImages: { en: 'No pictures or figures were found.', ar: 'لم يتم العثور على صور أو أشكال.' },
    noTables: { en: 'No tables were found.', ar: 'لم يتم العثور على جداول.' },
    tableMeta: { en: 'Page {page} · {rows} rows × {cols} columns', ar: 'الصفحة {page} · {rows} صفوف × {cols} أعمدة' },
    mdTruncated: { en: 'Only the beginning is shown here. The full file is in the ZIP.', ar: 'يظهر هنا الجزء الأول فقط. الملف الكامل موجود في ملف ZIP.' },
    w_usedCpu: { en: 'Tesseract read this file because Unlimited-OCR isn’t available on this computer.', ar: 'قرأ Tesseract هذا الملف لأن Unlimited-OCR غير متاح على هذا الجهاز.' },
    w_keptText: { en: 'Pages {pages} already had their own text, so it was kept as it is.', ar: 'الصفحات {pages} تحتوي على نص أصلاً، لذلك تُرك كما هو.' },
    w_noText: { en: 'No text was found on pages {pages}. If they do have text, try the Small print resolution.', ar: 'لم يتم العثور على نص في الصفحات {pages}. إذا كانت تحتوي على نص فجرّب دقة الخط الصغير.' },

    footer: {
      en: 'Offline tool: no internet, no cloud AI, no accounts. Your files stay on this computer.',
      ar: 'أداة تعمل دون إنترنت: بلا ذكاء اصطناعي سحابي ولا حسابات. تبقى ملفاتك على هذا الجهاز.',
    },
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

  let lang = 'en';

  function t(key, vars) {
    const entry = S[key];
    let s = entry ? (entry[lang] || entry.en) : key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split('{' + k + '}').join(String(v));
    return s;
  }

  function langName(code) {
    const n = LANG_NAMES[code];
    return n ? n[lang === 'ar' ? 1 : 0] : code;
  }

  function setLang(l) {
    lang = l === 'ar' ? 'ar' : 'en';
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
    for (const el of document.querySelectorAll('[data-lang]')) el.setAttribute('aria-pressed', String(el.dataset.lang === lang));
  }

  function num(n) {
    try { return new Intl.NumberFormat('en-US').format(n); } catch (e) { return String(n); }   // Western digits in both languages
  }

  H.i18n = { t, setLang, langName, num, has: (k) => k in S, get lang() { return lang; } };
})(window.HOCR = window.HOCR || {});
