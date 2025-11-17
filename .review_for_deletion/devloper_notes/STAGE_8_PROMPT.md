# System Prompt: Stage 8 - Advanced Authentication (Passkeys / WebAuthn)

## Context

You are implementing **Stage 8** of the Brainda project. The previous stages are **already complete**:

- ✅ Stages 0-4: MVP
- ✅ Stage 5: Mobile app with full idempotency
- ✅ Stage 6: Internal calendar with weekly views
- ✅ Stage 7: Google Calendar sync

## Your Mission: Stage 8

Upgrade authentication to support **multi-user scenarios** with:
- **Passkeys (WebAuthn)**: Passwordless authentication using biometrics or security keys
- **TOTP backup**: Time-based one-time passwords for emergency recovery
- **Multi-user support**: Family members each get their own account with isolated data
- **Organization model**: Shared infrastructure, separate user vaults

## Why This Stage Matters

The current MVP uses:
- Single API token (works for solo user)
- No proper user registration flow
- No security key support

**Stage 8 enables**:
- **Family hosting**: Mom, Dad, kids each have their own account
- **Better security**: Biometric authentication (Face ID, Touch ID, Windows Hello)
- **No passwords**: Passkeys are phishing-resistant and easier to use
- **Recovery**: TOTP backup codes for when primary device is lost

**Decision Gate**: Only implement this if:
- [ ] You want to share Brainda with family members (multi-user)
- [ ] You want stronger security than API token
- [ ] You're comfortable with WebAuthn complexity

If you're solo user forever, you can skip this stage entirely.

---

## Deliverables

### 1. Database Schema

Create `migrations/006_add_multi_user_auth.sql`:

```sql
-- Stage 8: Multi-user authentication with passkeys

-- Organizations table (for family/team hosting)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Update users table for multi-user
ALTER TABLE users
ADD COLUMN organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
ADD COLUMN display_name TEXT,
ADD COLUMN role TEXT DEFAULT 'member',  -- owner, admin, member
ADD COLUMN is_active BOOLEAN DEFAULT TRUE;

-- Passkey credentials (WebAuthn)
CREATE TABLE passkey_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id TEXT NOT NULL UNIQUE,  -- WebAuthn credential ID (base64url)
    public_key TEXT NOT NULL,  -- Public key (PEM format)
    counter INTEGER NOT NULL DEFAULT 0,  -- Sign counter (prevents replay attacks)
    transports TEXT[],  -- usb, nfc, ble, internal
    device_name TEXT,  -- User-friendly name: "MacBook Pro Touch ID"
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TOTP secrets (for 2FA backup)
CREATE TABLE totp_secrets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    secret TEXT NOT NULL,  -- Base32 encoded secret
    enabled BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    backup_codes TEXT[],  -- Array of one-time backup codes
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions (replace API token with proper sessions)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,  -- Secure random token
    device_name TEXT,
    device_type TEXT,  -- web, ios, android
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log for auth events
CREATE TABLE auth_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    event_type TEXT NOT NULL,  -- login_success, login_failed, passkey_added, etc.
    ip_address INET,
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_passkey_creds_user ON passkey_credentials(user_id);
CREATE INDEX idx_totp_user ON totp_secrets(user_id);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
CREATE INDEX idx_auth_audit_user ON auth_audit_log(user_id, created_at);
CREATE INDEX idx_users_org ON users(organization_id);
```

---

### 2. WebAuthn Implementation

#### A. Dependencies

```bash
# Install WebAuthn library
pip install py-webauthn
```

#### B. Passkey Registration

**File**: `app/api/routers/auth.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
)
import os
import secrets

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")  # Your domain
RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "Brainda Personal Assistant")
ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:3000")


@router.post("/register/begin")
async def begin_passkey_registration(
    email: str,
    display_name: str,
):
    """
    Start passkey registration flow.
    Returns challenge and options for WebAuthn ceremony.
    """

    # Check if user already exists
    existing = await db.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create user record (inactive until passkey registered)
    user = await db.create_user(
        email=email,
        display_name=display_name,
        is_active=False,
    )

    # Generate WebAuthn registration options
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=str(user.id).encode(),
        user_name=email,
        user_display_name=display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key="preferred",  # Enable discoverable credentials
        ),
    )

    # Store challenge in Redis (expires in 5 minutes)
    await redis.setex(
        f"webauthn_challenge:{user.id}",
        300,
        options.challenge.decode()
    )

    return {
        "user_id": str(user.id),
        "options": options.json(),
    }


@router.post("/register/complete")
async def complete_passkey_registration(
    user_id: str,
    credential: dict,  # From navigator.credentials.create()
    device_name: str = None,
):
    """
    Complete passkey registration.
    Verifies attestation and stores credential.
    """

    # Get stored challenge
    challenge = await redis.get(f"webauthn_challenge:{user_id}")
    if not challenge:
        raise HTTPException(status_code=400, detail="Challenge expired or invalid")

    try:
        # Verify registration response
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge.encode(),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )

        # Store credential
        await db.create_passkey_credential(
            user_id=user_id,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            transports=credential.get('transports', []),
            device_name=device_name or "Unknown Device",
        )

        # Activate user
        await db.update_user(user_id, {"is_active": True})

        # Clean up challenge
        await redis.delete(f"webauthn_challenge:{user_id}")

        # Log event
        await db.log_auth_event(
            user_id=user_id,
            event_type="passkey_registered",
            metadata={"device_name": device_name},
        )

        return {"success": True, "message": "Passkey registered successfully"}

    except Exception as e:
        logger.error("passkey_registration_failed", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")


@router.post("/login/begin")
async def begin_passkey_login():
    """
    Start passkey authentication flow.
    Returns challenge for WebAuthn ceremony.
    """

    # Generate authentication options
    options = generate_authentication_options(
        rp_id=RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    # Store challenge in Redis
    challenge_id = secrets.token_urlsafe(32)
    await redis.setex(
        f"webauthn_auth_challenge:{challenge_id}",
        300,
        options.challenge.decode()
    )

    return {
        "challenge_id": challenge_id,
        "options": options.json(),
    }


@router.post("/login/complete")
async def complete_passkey_login(
    challenge_id: str,
    credential: dict,  # From navigator.credentials.get()
    request: Request,
):
    """
    Complete passkey authentication.
    Verifies signature and creates session.
    """

    # Get stored challenge
    challenge = await redis.get(f"webauthn_auth_challenge:{challenge_id}")
    if not challenge:
        raise HTTPException(status_code=400, detail="Challenge expired")

    # Find credential in database
    credential_id = credential['id']
    stored_cred = await db.get_passkey_credential_by_id(credential_id)
    if not stored_cred:
        raise HTTPException(status_code=400, detail="Credential not found")

    try:
        # Verify authentication response
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.encode(),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
            credential_public_key=stored_cred.public_key,
            credential_current_sign_count=stored_cred.counter,
        )

        # Update sign counter (prevents replay attacks)
        await db.update_passkey_credential(
            stored_cred.id,
            {
                "counter": verification.new_sign_count,
                "last_used_at": datetime.utcnow(),
            }
        )

        # Create session
        session_token = secrets.token_urlsafe(48)
        session = await db.create_session(
            user_id=stored_cred.user_id,
            token=session_token,
            device_name=stored_cred.device_name,
            device_type="web",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        # Log event
        await db.log_auth_event(
            user_id=stored_cred.user_id,
            event_type="login_success",
            ip_address=request.client.host,
            metadata={"device_name": stored_cred.device_name},
        )

        # Clean up challenge
        await redis.delete(f"webauthn_auth_challenge:{challenge_id}")

        return {
            "success": True,
            "session_token": session_token,
            "expires_at": session.expires_at.isoformat(),
        }

    except Exception as e:
        # Log failed attempt
        await db.log_auth_event(
            event_type="login_failed",
            ip_address=request.client.host,
            metadata={"error": str(e)},
        )

        logger.error("passkey_auth_failed", extra={"error": str(e)})
        raise HTTPException(status_code=401, detail="Authentication failed")


@router.post("/logout")
async def logout(current_user = Depends(get_current_user)):
    """
    Logout: invalidate current session.
    """
    session_token = current_user.session_token  # From auth middleware
    await db.delete_session(session_token)

    return {"success": True, "message": "Logged out"}
```

---

### 3. TOTP Backup (Emergency Recovery)

**File**: `app/api/routers/totp.py`

```python
import pyotp
import qrcode
import io
import base64

@router.post("/totp/setup")
async def setup_totp(current_user = Depends(get_current_user)):
    """
    Generate TOTP secret for 2FA backup.
    Returns QR code for authenticator app.
    """

    # Generate secret
    secret = pyotp.random_base32()

    # Generate backup codes (10 one-time codes)
    backup_codes = [secrets.token_hex(4) for _ in range(10)]

    # Store in database (not enabled until verified)
    await db.create_totp_secret(
        user_id=current_user.id,
        secret=secret,
        backup_codes=backup_codes,
        enabled=False,
    )

    # Generate QR code
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="Brainda",
    )

    qr = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_base64}",
        "backup_codes": backup_codes,
    }


@router.post("/totp/verify")
async def verify_totp(
    code: str,
    current_user = Depends(get_current_user),
):
    """
    Verify TOTP code and enable 2FA.
    """

    totp_record = await db.get_totp_secret(current_user.id)
    if not totp_record:
        raise HTTPException(status_code=400, detail="TOTP not set up")

    totp = pyotp.TOTP(totp_record.secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")

    # Enable TOTP
    await db.update_totp_secret(totp_record.id, {
        "enabled": True,
        "verified_at": datetime.utcnow(),
    })

    return {"success": True, "message": "TOTP enabled"}


@router.post("/totp/authenticate")
async def authenticate_with_totp(
    user_id: str,
    code: str,
):
    """
    Authenticate with TOTP code (backup method).
    """

    totp_record = await db.get_totp_secret(user_id)
    if not totp_record or not totp_record.enabled:
        raise HTTPException(status_code=400, detail="TOTP not enabled")

    totp = pyotp.TOTP(totp_record.secret)

    # Check TOTP code
    if totp.verify(code, valid_window=1):
        # Create session
        session_token = secrets.token_urlsafe(48)
        session = await db.create_session(
            user_id=user_id,
            token=session_token,
            device_type="web",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        return {
            "success": True,
            "session_token": session_token,
        }

    # Check backup codes
    if code in totp_record.backup_codes:
        # Remove used backup code
        remaining_codes = [c for c in totp_record.backup_codes if c != code]
        await db.update_totp_secret(totp_record.id, {
            "backup_codes": remaining_codes,
        })

        # Create session
        session_token = secrets.token_urlsafe(48)
        session = await db.create_session(
            user_id=user_id,
            token=session_token,
            device_type="web",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        return {
            "success": True,
            "session_token": session_token,
            "message": f"Backup code used. {len(remaining_codes)} remaining.",
        }

    raise HTTPException(status_code=401, detail="Invalid code")
```

---

### 4. Frontend (Web)

#### A. Passkey Registration Flow

**File**: `app/web/components/PasskeyRegister.tsx`

```typescript
import React, { useState } from 'react';
import api from '@/lib/api';

export default function PasskeyRegister() {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Step 1: Begin registration
      const beginResponse = await api.post('/auth/register/begin', {
        email,
        display_name: displayName,
      });

      const { user_id, options } = beginResponse.data;
      const publicKeyOptions = JSON.parse(options);

      // Step 2: Create credential with WebAuthn
      const credential = await navigator.credentials.create({
        publicKey: {
          ...publicKeyOptions,
          challenge: Uint8Array.from(atob(publicKeyOptions.challenge), c => c.charCodeAt(0)),
        },
      });

      if (!credential) {
        throw new Error('Credential creation failed');
      }

      // Step 3: Complete registration
      await api.post('/auth/register/complete', {
        user_id,
        credential: {
          id: credential.id,
          rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
          response: {
            clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
            attestationObject: btoa(String.fromCharCode(...new Uint8Array(credential.response.attestationObject))),
          },
          type: credential.type,
        },
        device_name: deviceName || 'My Device',
      });

      alert('Registration successful! You can now log in with your passkey.');
      window.location.href = '/login';

    } catch (error) {
      console.error('Registration error:', error);
      alert(`Registration failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleRegister}>
      <h2>Register with Passkey</h2>

      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />
      </label>

      <label>
        Display Name
        <input
          type="text"
          value={displayName}
          onChange={e => setDisplayName(e.target.value)}
          required
        />
      </label>

      <label>
        Device Name (optional)
        <input
          type="text"
          value={deviceName}
          onChange={e => setDeviceName(e.target.value)}
          placeholder="MacBook Pro"
        />
      </label>

      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create Passkey'}
      </button>

      <p>
        Use Touch ID, Face ID, or a security key to create a secure passkey.
      </p>
    </form>
  );
}
```

#### B. Passkey Login Flow

**File**: `app/web/components/PasskeyLogin.tsx`

```typescript
import React, { useState } from 'react';
import api from '@/lib/api';

export default function PasskeyLogin() {
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);

    try {
      // Step 1: Begin authentication
      const beginResponse = await api.post('/auth/login/begin');
      const { challenge_id, options } = beginResponse.data;
      const publicKeyOptions = JSON.parse(options);

      // Step 2: Get credential from authenticator
      const credential = await navigator.credentials.get({
        publicKey: {
          ...publicKeyOptions,
          challenge: Uint8Array.from(atob(publicKeyOptions.challenge), c => c.charCodeAt(0)),
        },
      });

      if (!credential) {
        throw new Error('Authentication cancelled');
      }

      // Step 3: Complete authentication
      const completeResponse = await api.post('/auth/login/complete', {
        challenge_id,
        credential: {
          id: credential.id,
          rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
          response: {
            clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
            authenticatorData: btoa(String.fromCharCode(...new Uint8Array(credential.response.authenticatorData))),
            signature: btoa(String.fromCharCode(...new Uint8Array(credential.response.signature))),
          },
          type: credential.type,
        },
      });

      const { session_token } = completeResponse.data;

      // Store session token
      localStorage.setItem('session_token', session_token);

      // Redirect to app
      window.location.href = '/chat';

    } catch (error) {
      console.error('Login error:', error);
      alert(`Login failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Login with Passkey</h2>

      <button onClick={handleLogin} disabled={loading}>
        {loading ? 'Authenticating...' : 'Sign In'}
      </button>

      <p>
        Use Touch ID, Face ID, or your security key to sign in.
      </p>
    </div>
  );
}
```

---

## Acceptance Criteria

### Passkey Registration

- [ ] User can register with email + biometric/security key
- [ ] Registration works on: macOS (Touch ID), iOS (Face ID), Android (fingerprint), Windows (Hello), YubiKey
- [ ] Credential stored securely in database
- [ ] User marked as active after successful registration

### Passkey Login

- [ ] User can login with passkey (no password)
- [ ] Session created with 30-day expiry
- [ ] Session token stored in localStorage (web) or SecureStore (mobile)
- [ ] Failed login attempts logged in auth_audit_log

### TOTP Backup

- [ ] User can enable TOTP via authenticator app (Google Authenticator, Authy, 1Password)
- [ ] QR code displays correctly
- [ ] 10 backup codes generated
- [ ] TOTP code works as alternative login method
- [ ] Backup codes work once and are removed after use

### Multi-User Support

- [ ] Multiple users can register on same Brainda instance
- [ ] Each user's data isolated (notes, reminders, documents)
- [ ] Organization model supports family hosting
- [ ] Audit log tracks all auth events per user

---

## Testing Strategy

### Manual Testing

**Test 1: Passkey Registration (macOS)**

1. Open registration page
2. Enter email: test@example.com
3. Click "Create Passkey"
4. Touch ID prompt appears → authenticate
5. Verify: User created in database, credential stored

**Test 2: Passkey Login**

1. Open login page
2. Click "Sign In"
3. Touch ID prompt appears → authenticate
4. Verify: Session created, redirected to chat

**Test 3: TOTP Setup**

1. Login with passkey
2. Go to Security Settings
3. Click "Enable TOTP"
4. Scan QR code with Google Authenticator
5. Enter 6-digit code
6. Verify: TOTP enabled, backup codes shown

**Test 4: Multi-User Isolation**

1. Register User A
2. Create note as User A
3. Logout
4. Register User B
5. Verify: User B cannot see User A's notes

---

## Security Checklist

- [ ] **Challenge entropy**: Use cryptographically secure random for WebAuthn challenges
- [ ] **Replay protection**: Verify sign counter increments on each authentication
- [ ] **Origin validation**: Verify expected origin matches in WebAuthn responses
- [ ] **Session security**: Use httpOnly, secure, sameSite cookies for session tokens
- [ ] **TOTP timing**: Use valid_window=1 to allow 30s clock drift
- [ ] **Backup codes**: Hash backup codes before storing (bcrypt or similar)
- [ ] **Rate limiting**: Max 5 failed login attempts per hour per IP
- [ ] **Audit logging**: Log all auth events with timestamps and IPs

---

## Performance Targets

- [ ] Passkey registration: <3s end-to-end
- [ ] Passkey login: <2s end-to-end
- [ ] TOTP verification: <100ms
- [ ] Session lookup: <10ms (indexed query)

---

## Migration Guide

### For Existing MVP Users

**Option 1: Migrate API Token to Passkey**

```bash
# Run migration script
python scripts/migrate_api_token_to_passkey.py

# Prompts:
# - Email: user@example.com
# - Display Name: Your Name
# - Creates passkey registration link
# - User completes registration via link
```

**Option 2: Keep API Token (Backward Compatible)**

```python
# Update auth middleware to support both:
# 1. Authorization: Bearer <token> (legacy)
# 2. Authorization: Bearer <session_token> (new)

async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401)

    token = authorization.split(" ")[1]

    # Try session token first
    session = await db.get_session_by_token(token)
    if session and session.expires_at > datetime.utcnow():
        return session.user

    # Fallback to legacy API token
    if token == os.getenv("API_TOKEN"):
        return await db.get_default_user()

    raise HTTPException(401, detail="Invalid token")
```

---

## Risk Checklist

- [ ] **Browser support**: WebAuthn not supported in old browsers (provide fallback)
- [ ] **Device loss**: If user loses device + backup codes, account recovery is HARD
- [ ] **Complexity**: WebAuthn is complex, thorough testing required
- [ ] **Mobile**: Ensure passkey works on mobile (iOS/Android WebAuthn support)
- [ ] **Sync**: Passkeys can sync via iCloud/Google Password Manager (educate users)

---

## Success Metrics

After 1 month:

- **Adoption**: >80% of new users choose passkey over API token
- **Login time**: <5s average (faster than password)
- **Support requests**: <5% of users need help with setup
- **Security**: 0 account compromises

---

## References

- [WebAuthn Guide](https://webauthn.guide/)
- [py-webauthn Documentation](https://github.com/duo-labs/py_webauthn)
- [SimpleWebAuthn (Frontend)](https://simplewebauthn.dev/)
- [Passkeys.dev](https://passkeys.dev/)

---

## Remember

**Do NOT implement testing yet.** Focus on making the functionality work. Comprehensive tests will be written after all stages are complete.

Good luck! 🚀
