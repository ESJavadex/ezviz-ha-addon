# EZVIZ Camera Add-ons for Home Assistant

This repository contains Home Assistant add-ons for EZVIZ cameras.

## Add-ons

### [EZVIZ Camera Stream](./ezviz-camera)

Stream video from EZVIZ cameras directly to Home Assistant without cloud dependencies.

## Installation

1. Open Home Assistant
2. Go to **Settings** → **Add-ons** → **Add-on Store**
3. Click the menu (⋮) in the top right → **Repositories**
4. Add this repository URL:
   ```
   https://github.com/ESJavadex/ezviz-ha-addon
   ```
5. Click **Add** → **Close**
6. Find "EZVIZ Camera Stream" in the add-on store and install it

## Device verification (MFA)

The first time the add-on logs in, EZVIZ may refuse to recognise it as a known
device and reply with `meta.code 6002`. When that happens the add-on asks EZVIZ
to send a verification code to your account and writes this to the log:

```
✗ EZVIZ pide verificar este dispositivo.
  Se acaba de enviar un código a tu cuenta de EZVIZ (email o SMS).
  Ponlo en la opción 'mfa_code' del add-on y reinícialo.
```

Put that code in the **`mfa_code`** option and restart the add-on. It is only
needed once: the login registers this installation as a trusted terminal and
subsequent logins go through without a code. You can leave the option filled in
or clear it afterwards; it is ignored once the terminal is registered.

The identity being registered is a `featureCode` generated on first run and
stored in `/data/feature_code`, which survives restarts and updates. Earlier
versions sent a fixed string of 32 zeros, shared by every installation, which is
what EZVIZ started rejecting. **Do not delete that file** — losing it means
verifying again.

The add-on also keeps the session in `/data/session.json` and renews it instead
of logging in again on every start, so a restart no longer risks running into
device verification at all.

## Troubleshooting

**Login fails repeatedly.** The log now prints the reason EZVIZ gave instead of
a generic `Login failed`, including whether it is a wrong password, a locked
account or the wrong region. After an authentication failure the add-on backs
off (60s, doubling up to 30 min) instead of retrying immediately, so a bad
configuration cannot hammer the EZVIZ API.

**The stream is frozen but the add-on looks healthy.** Check that
`#EXT-X-MEDIA-SEQUENCE` in `http://<host>:8080/stream.m3u8` keeps increasing. If
it does not, the add-on is serving stale segments and cannot reach the camera.
