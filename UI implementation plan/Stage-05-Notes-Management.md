# Stage 5: Notes Management

**Duration**: 2-3 days
**Priority**: HIGH
**Dependencies**: Stages 1, 2, 3

---

## Goal

Build full notes interface with create, edit, view, delete, tags, and search capabilities.

---

## Key Components

- **NotesPage**: Grid/list view with filters
- **NoteCard**: Preview with title, body, tags
- **NoteEditor**: Full markdown editor
- **NoteDetail**: Read-only view with actions
- **TagInput**: Autocomplete tag selector

---

## Dependencies to Install

npm install react-markdown remark-gfm

---

## Testing Checklist

- [ ] Can create notes
- [ ] Can edit notes
- [ ] Can delete notes
- [ ] Tags autocomplete works
- [ ] Markdown rendering works
- [ ] Search filters notes
- [ ] Mobile responsive

---

## Deliverables

- [x] Notes CRUD operations\n- [x] Markdown editor\n- [x] Tag management\n- [x] Search/filter

---

## Next Stage

Can proceed to Stages 12-13 after all pages (4-11) complete.

---

## Additional Notes

Reuse existing components from app/web/components/ where possible. Focus on integration with backend API.
