# Stage 10: Authentication Flow

**Duration**: 2-3 days
**Priority**: HIGH
**Dependencies**: Stages 1, 2, 3

---

## Goal

Implement login, registration with passkeys/TOTP, and session management.

---

## Key Components

- **LoginPage**: Login options (passkey/TOTP)
- **RegisterPage**: Signup with passkey setup
- **PasskeyLogin**: WebAuthn login (already exists, refactor)
- **PasskeyRegister**: WebAuthn registration (already exists, refactor)
- **ProtectedRoute**: Auth guard wrapper
- **UserMenu**: Dropdown with logout

---

## Dependencies to Install

# Passkey dependencies already in place

---

## Testing Checklist

- [ ] Passkey login works
- [ ] Passkey registration works
- [ ] TOTP login works
- [ ] Session persists
- [ ] Protected routes redirect
- [ ] Logout works

---

## Deliverables

- [x] Login/register flows\n- [x] Passkey integration\n- [x] Session management\n- [x] Protected routes

---

## Next Stage

Can proceed to Stages 12-13 after all pages (4-11) complete.

---

## Additional Notes

Integrate existing PasskeyLogin.tsx and PasskeyRegister.tsx. Add TOTP as backup auth method.
