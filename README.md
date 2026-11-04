# AI Control Center — مركز التحكم بالذكاء الاصطناعي

> **مستودع معرض عام | Public portfolio repository**  
> مستودع التطوير الخاص منفصل عن هذا المستودع. | The private development repository is separate from this repository.  
> **حالة الإصدار | Release status:** راجع أحدث Release وTag في GitHub؛ هذا الملف لا يفترض أن رقم الإصدار المذكور في وثائق أقدم ما زال هو الأحدث.  
> Check the latest GitHub Release and tag; this README does not assume that a version number from older documentation is still current.

## نظرة عامة | Overview

AI Control Center بيئة ذكاء اصطناعي محلية على Windows، هدفها إبقاء التحكم بالنماذج والذاكرة والمشاريع والتدريب والأدوات والصلاحيات والتكاملات السحابية الاختيارية بيد المستخدم.

AI Control Center is a local-first Windows AI environment focused on keeping the user in control of models, memory, projects, training, tools, permissions, and optional cloud integrations.

## الاتجاه والقدرات المستهدفة | Direction and intended capabilities

يهدف المشروع إلى جمع هذه القدرات داخل بيئة سطح مكتب واحدة:
The project aims to combine these capabilities in one desktop environment:

- نماذج ذكاء اصطناعي محلية. — Local AI models.
- ذاكرة محلية وسياق للمشاريع. — Local memory and project context.
- مساحات عمل للمشاريع. — Project workspaces.
- مسارات Teacher وDataset. — Teacher and Dataset workflows.
- تدريب Student باستخدام LoRA / QLoRA. — Student training with LoRA / QLoRA.
- فحوص GPU / CUDA / VRAM. — GPU / CUDA / VRAM checks.
- مسارات Git / GitHub. — Git / GitHub workflows.
- التحكم بالشبكة. — Network controls.
- توجيه الأفعال وفحص الصلاحيات. — Action routing and permission checks.
- إعداد Windows وإدارة المكونات الاختيارية. — Windows setup and optional component management.

## مسار تنفيذ الأوامر بأمان | Safe action execution flow

النموذج غير مصمم لتنفيذ أوامر Shell عشوائية مباشرة. المسار المقصود هو:
The model is not intended to execute arbitrary shell commands directly. The intended execution path is:

```text
AI
↓
Action Router
↓
Permission Check
↓
Owner Approval when required
↓
Execution
↓
Audit
```

## سياسة المستودع العام | Public repository policy

هذا المستودع منفصل عمدًا عن مستودع التطوير الخاص، ولا ينبغي أن يحتوي على:
This repository is intentionally separated from the private development repository and must not contain:

- الذاكرة الشخصية أو المشاريع الخاصة. — Personal memory or private projects.
- مفاتيح API أو بيانات اعتماد. — API keys or credentials.
- مجموعات بيانات خاصة. — Private datasets.
- سجلات التشغيل أو النسخ الاحتياطية. — Runtime logs or backups.
- ملفات النماذج المحلية. — Local model files.
- بيئات التدريب أو نقاط الحفظ. — Training environments or checkpoints.
- مسارات مساحات العمل الخاصة. — Private workspace paths.

المكونات الاختيارية الثقيلة، مثل النماذج المحلية وبيئة التدريب، يُفترض تجهيزها عند الطلب عبر مدير الإعداد داخل التطبيق بدل تضمينها داخل مستودع المصدر.

Heavy optional components, such as local models and the training environment, are intended to be installed on demand through the application's Setup Manager rather than bundled into the source repository.

## محاور التطوير الموثقة | Documented development focus

تتضمن محاور التطوير الموثقة:
Documented development focus includes:

- تدريب Student فعلي باستخدام LoRA / QLoRA. — Real LoRA / QLoRA Student training.
- اختيار النموذج الأساسي. — Base Model selection.
- عرض Progress / Epoch / Step / Loss. — Progress / Epoch / Step / Loss reporting.
- مراقبة VRAM. — VRAM monitoring.
- الإيقاف الآمن ونقاط الحفظ. — Safe Stop and checkpoints.
- حفظ LoRA Adapter. — LoRA Adapter saving.
- مقارنة النموذج الأساسي والمدرّب. — Base-vs-trained evaluation.
- فحص التحديثات. — Update checks.
- النسخ الاحتياطي والتحقق والاسترجاع أثناء التحديث. — Backup, verification, and rollback during updates.

هذه قائمة اتجاهات موثقة وليست إقرارًا بأن كل بند مكتمل في النسخة الحالية. تُراجع حالة كل ميزة من أحدث المهام والـCommits والاختبارات.

This is a documented direction, not a claim that every item is complete in the current build. Verify each feature's status using the latest issues, commits, and test evidence.

## المطوّر | Developer

**@rakan77jjjjj**  
GitHub: **@rakan77jjjjj**

## سياسة اللغة | Language policy

كل توثيق جديد أو معدّل في هذا المستودع يكون بالعربية والإنجليزية معًا، والعربية أولًا. تبقى أسماء الكود والملفات والأوامر والمعرفات التقنية كما هي.

All new or edited documentation in this repository must be bilingual (Arabic + English), Arabic first. Code identifiers, filenames, commands, and technical names remain unchanged.
