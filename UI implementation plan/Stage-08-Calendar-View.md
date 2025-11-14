# Stage 8: Calendar View

**Duration**: 2-3 days
**Priority**: MEDIUM
**Dependencies**: Stages 1, 2, 3

---

## Goal

Build calendar interface with week/month views, event management, and Google Calendar sync.

---

## Key Components

- **CalendarPage**: View toggle (Week/Month)
- **WeeklyCalendar**: 7-day grid (already exists, refactor)
- **MonthlyCalendar**: Month view grid
- **EventForm**: Create/edit events
- **GoogleCalendarConnect**: Sync integration (already exists)

---

## Dependencies to Install

npm install date-fns rrule

---

## Testing Checklist

- [ ] Week view displays events
- [ ] Month view works
- [ ] Can create events
- [ ] RRULE events show recurring
- [ ] Google Calendar sync works
- [ ] Mobile responsive

---

## Deliverables

- [x] Week/month views\n- [x] Event creation\n- [x] RRULE support\n- [x] Google Calendar sync

---

## Next Stage

Can proceed to Stages 12-13 after all pages (4-11) complete.

---

## Additional Notes

Refactor existing WeeklyCalendar.tsx. Add month view. Integrate GoogleCalendarConnect.tsx.
