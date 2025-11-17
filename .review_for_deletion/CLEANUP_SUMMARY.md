# Cleanup Summary - Files Moved for Review

This directory contains files that have been identified for potential deletion during the codebase cleanup on 2025-11-17.

## Directory Structure

### test_logs/
**17 test log files** - Temporary test execution outputs that should not be in version control
- final_full_run.log
- full_run_1.log
- stage0.log through stage8.log
- test_run.log, test_stage2*.log
- tests_full_run.log

**Recommendation**: Safe to delete - these are temporary test artifacts.

### temp_files/
**2 temporary development files**
- test.py - Single line test file
- tmp_dockerfile_dump.txt - Temporary Dockerfile dump

**Recommendation**: Safe to delete - temporary development artifacts.

### redundant_docs/
**7 documentation files** that are either outdated, redundant, or superseded by other docs
- CALENDAR_ENDPOINT_ANALYSIS.md - Historical calendar endpoint analysis
- CLAUDE_FULL.md - Stub file (28 lines) with hardcoded path
- FILEWATCHER_CODEFLOW.md - Redundant with FILE_WATCHER_README.md and FILE_WATCHER_ANALYSIS.md
- FRESH_START.md - Documentation from "fresh start" effort
- TEST_FAILURES_ANALYSIS.md - Historical test failure analysis
- TEST_FAILURE_ROOT_CAUSE_ANALYSIS.md - Another test failure analysis
- init.sql - Large schema file (184 lines) that duplicates what's in migrations/

**Recommendation**: Review content before deleting. Most are historical analysis documents. The init.sql should be deleted as migrations/ is the source of truth.

### legacy_frontend/components/
**9 legacy React components** - Old component directory structure
- BraindaInterface.tsx, CitationRenderer.tsx, DocumentList.tsx, DocumentUpload.tsx
- GoogleCalendarConnect.tsx, PasskeyLogin.tsx, PasskeyRegister.tsx
- ReminderList.tsx, WeeklyCalendar.tsx

**Context**: These components have been superseded by the new organized structure in app/web/src/components/ which has 109 files properly organized into subdirectories (auth/, calendar/, chat/, documents/, layout/, notes/, reminders/, search/, settings/, shared/, tasks/).

**Recommendation**: Review for any unique functionality not migrated to the new structure, then delete. The new structure in src/components/ should be the canonical location.

### UI implementation plan/
**Complete directory** - UI implementation planning documents

**Recommendation**: Review if historical documentation is needed, otherwise safe to delete.

### Previous cleanup artifacts/
The following directories existed before this cleanup:
- old_test_scripts/ - 4 duplicate test scripts
- ai_generated_docs/ - 13 AI-generated analysis/review documents
- devloper_notes/ (typo in name) - 11 development stage prompts and working notes

## Additional Cleanup Recommendations

### Migration File Numbering
Multiple migrations share the same sequence numbers (in migrations/ directory):
- 002_add_reminders.sql and 002_fix_dedup_index.sql
- 003_add_documents.sql and 003_fix_dedup_index_again.sql
- 005_add_calendar.sql and 005_notes_unique_title.sql
- 006_add_idempotency.sql and 006_add_multi_user_auth.sql

**Action Required**: Renumber migrations to have unique sequential IDs.

### File Watcher Documentation Consolidation
Three separate file watcher documents exist:
- FILE_WATCHER_README.md
- FILE_WATCHER_ANALYSIS.md
- FILEWATCHER_CODEFLOW.md (moved to review)

**Recommendation**: Consolidate into a single comprehensive file watcher guide.

### Root Directory Organization
After cleanup, the root directory should have significantly fewer markdown files. Consider moving detailed analysis/guide docs to the docs/ directory to keep the root clean.

## How to Proceed

1. **Review each directory** in this folder
2. **Verify no unique functionality** is being lost (especially in legacy_frontend/)
3. **Delete this entire .review_for_deletion directory** when satisfied
4. **Address migration renumbering** separately
5. **Consider consolidating** file watcher documentation

## Files Kept (Not Moved)

The following files were intentionally kept in their locations:
- CLAUDE.md - Active Claude Code instructions
- README.md - Main project documentation
- DEVELOPMENT.md - Active development guide
- DOCKER_SETUP.md - Active Docker configuration guide
- FILE_WATCHER_README.md, FILE_WATCHER_ANALYSIS.md - Active file watcher docs (consider consolidating)
- PRODUCTION_READY.md - Production readiness checklist
- IMPROVEMENTS_SUMMARY.md - Recent improvements summary
- Agents.md - Development guidelines
- All files in app/, tests/, migrations/, docs/, scripts/ directories
