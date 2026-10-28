# دليل المساهمة

## Git Workflow
نستخدم **Git Flow** المبسط.

## Commit Message Convention
نستخدم Conventional Commits: feat, fix, docs, test, refactor, chore.

## Code Style
```bash
ruff format .
ruff check . --fix
```

## Pull Request Checklist
- ☐ الكود يمر pytest
- ☐ التغطية لا تقل عن 80%
- ☐ ruff check . نظيف
- ☐ الوصف يشرح: ماذا؟ ولماذا؟
