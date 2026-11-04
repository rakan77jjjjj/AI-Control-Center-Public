# سياسة التوثيق ثنائية اللغة | Bilingual Documentation Policy

## القاعدة | Rule
اكتب كل نص بشري جديد أو معدّل في GitHub بالعربية والإنجليزية معًا، واجعل العربية أولًا، ثم ترجمة إنجليزية تحمل المعنى نفسه.
Write all new or edited human-facing GitHub text in Arabic and English, Arabic first, followed by an English version with the same meaning.

تنطبق القاعدة على README وIssues وPRs والتعليقات والوثائق وخطط العمل وسجلات القرارات وتقارير الحالة وأدلة التثبيت والتشغيل والاختبار.
This applies to README, issues, pull requests, comments, documentation, plans, decision logs, status reports, installation instructions, runbooks, and test guides.

## ما يبقى كما هو | Keep unchanged
لا تترجم ولا تعِد تسمية: أسماء الملفات والمسارات والفروع، الدوال والمتغيرات والفئات والحزم، مفاتيح JSON/YAML، APIs، أعلام CLI، أوامر الطرفية ورسائل الخطأ الحرفية.
Do not translate or rename filenames, paths, branches, functions, variables, classes, packages, JSON/YAML keys, APIs, CLI flags, terminal commands, or exact error strings.

## تحديث المحتوى القديم | Existing content
ترجم الوثائق القديمة على دفعات صغيرة قابلة للمراجعة. لا تعِد كتابة Git history أو تمسح التعليقات السابقة. ابدأ بـREADME وتعليمات الوكلاء ودليل التشغيل والمهام المفتوحة.
Translate legacy documentation in small reviewable batches. Do not rewrite Git history or erase old comments. Start with README, agent instructions, run guides, and open-task tracking.

## دقة الحالة | Accurate status
ميّز بين موجود في الكود، مدمج، مختبر، ومُطلق. اذكر الاختبارات الفعلية فقط، وحدد ما لم يُختبر.
Distinguish implemented in code, merged, tested, and released. Report only tests actually run and explicitly identify what remains untested.

## خصوصية وأمان | Privacy and security
لا تنشر أسرارًا أو بيانات شخصية أو سجلات أو مسارات محلية حساسة في المستودعات العامة.
Never publish secrets, personal data, private logs, or sensitive local paths in public repositories.
