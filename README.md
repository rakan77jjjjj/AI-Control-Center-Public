# AI Control Center

> **Public portfolio repository**  
> **Current project version: 4.7.1 Beta**  
> **Active development: 4.8**

AI Control Center is a local-first Windows AI environment focused on keeping the user in control of models, memory, projects, training, tools, permissions, and optional cloud integrations.

## Current direction

The project is being built toward a single desktop environment that can combine:

- Local AI models
- Local memory and project context
- Project workspaces
- Teacher / Dataset workflows
- Student training with LoRA / QLoRA
- GPU / CUDA / VRAM checks
- Git / GitHub workflows
- Network controls
- Action routing and permission checks
- Windows setup and optional component management

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

## Public repository policy

This repository is intentionally separated from the private development repository.

It does **not** contain:

- Personal memory
- Personal projects
- API keys or credentials
- Private datasets
- Runtime logs
- Backups
- Local model files
- Training environments
- Checkpoints
- Private workspace paths

Heavy optional components such as local models and the training environment are intended to be installed on demand by the application's Setup Manager rather than bundled into the source repository.

## 4.8 focus

The next development milestone focuses on:

- Real LoRA / QLoRA Student training
- Base Model selection
- Progress / Epoch / Step / Loss
- VRAM monitoring
- Safe Stop
- Checkpoints
- LoRA Adapter saving
- Base vs Trained testing
- Update checks
- Backup / verification / rollback during updates

## Developer

**@rakan77jjjjj**

GitHub: **@rakan77jjjjj**

## Arabic

المشروع عبارة عن بيئة ذكاء اصطناعي محلية لويندوز، الهدف منها جمع المساعد والذاكرة والمشاريع والتدريب والأدوات في مكان واحد مع بقاء الصلاحيات والتحكم بيد المستخدم.

النسخة العامة هنا منفصلة عن مستودع التطوير الخاص، ولا تحتوي على بياناتي الشخصية أو الذاكرة أو المشاريع الخاصة أو المفاتيح أو السجلات أو النسخ الاحتياطية.

المكونات الثقيلة مثل بيئة التدريب والموديلات المحلية لن تُحشر داخل المستودع، بل الهدف أن يتم تنزيلها عند الحاجة من داخل البرنامج.
