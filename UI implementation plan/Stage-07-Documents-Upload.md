# Stage 7: Documents Upload

**Duration**: 2 days
**Priority**: MEDIUM
**Dependencies**: Stages 1, 2, 3

---

## Goal

Build document library with drag-drop upload, preview, and deletion.

---

## Key Components

- **DocumentsPage**: Library view with search/filter
- **DocumentUpload**: Drag-drop zone with progress
- **DocumentCard**: File info with actions
- **DocumentViewer**: PDF/text viewer modal

---

## Dependencies to Install

npm install react-dropzone

---

## Testing Checklist

- [ ] Drag-drop upload works
- [ ] Multiple files queue correctly
- [ ] Progress bars show
- [ ] Document viewer works
- [ ] Can delete documents
- [ ] Mobile responsive

---

## Deliverables

- [x] Document upload\n- [x] File preview\n- [x] Delete documents\n- [x] Upload progress

---

## Next Stage

Can proceed to Stages 12-13 after all pages (4-11) complete.

---

## Additional Notes

Refactor existing DocumentUpload.tsx component. Add document viewer for previewing uploaded files.
