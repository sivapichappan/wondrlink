# Auth email templates

**Codes everywhere, no links anywhere** — owner direction. Phone sign-in already
uses a one-time code; these six templates make every email do the same.

All six Supabase auth emails are kept in the repo because they are
**patient-facing copy** and because the app depends on their contents.

| File | Supabase template | Sent by | Confirmed with |
|---|---|---|---|
| `confirm_signup.html` | Confirm signup | `sign_up()` (Flask `/api/auth/register`) | `verifyOtp(type: 'signup')` |
| `reset_password.html` | Reset Password | `resetPasswordForEmail()` | `verifyOtp(type: 'recovery')` |
| `magic_link.html` | Magic Link | `signInWithOtp({email})` | `verifyOtp(type: 'email')` |
| `change_email.html` | Change Email Address | `updateUser({email})` | `verifyOtp(type: 'email_change')` |
| `invite.html` | Invite user | admin invite (dashboard or API) | `verifyOtp(type: 'invite')` |
| `reauthentication.html` | Reauthentication | `reauthenticate()` | `verifyOtp(type: 'reauthentication')` |

The app calls only the first two today. **The other four are here anyway**, because
Supabase's defaults for magic link, invite and change-email all contain
`{{ .ConfirmationURL }}` — and an unused template that sends a link is still a link
that can be sent: by a stray call, by a screen someone adds later, or by an admin
inviting a physician from the dashboard at 9pm. Reauthentication already defaults
to a code and is written out so the set is complete and checkable.

## The one thing that must not change

`{{ .Token }}` is what makes these **codes** instead of **links**. Supabase decides
between the two purely on what the template contains:

- `{{ .ConfirmationURL }}` → a link the user taps in a browser
- `{{ .Token }}` → a six digit code

Every app screen asks for a code. Swap a template back to the link version and the
user gets an email with nothing in it they can type. `tests/test_email_templates.py`
fails if that happens, for **all six**, and also fails if a seventh template file
appears that nobody added to the check.

## Applying them (dashboard, one time each)

1. Supabase dashboard → **Authentication → Emails**
2. Pick the template, paste that file's contents into the body
3. Subject: `Your Sage code` for all six (`Your Sage reset code` also fine for the
   reset one)
4. Save

The HTML deliberately uses tables and inline styles. Email clients drop `<style>`
blocks and most modern CSS, and Outlook needs the table.

## Order matters when shipping this

The app screens and the templates have to move close together:

- **Templates updated, old app still installed** → the user gets a code and the old
  screen only offers a "check your email for a link" message. No field to type it in.
- **App updated, templates still default** → the user gets a link and the new screen
  asks for a code they were never sent.

So: configure SMTP → paste all six templates → turn **Confirm email** on → ship the
app update (`eas update --channel production --platform ios`), close together.

## Before real users see this

**The built-in Supabase SMTP will not deliver to them.** Until custom SMTP is
configured, Supabase refuses any address that is not a member of the project's
organisation and the sender gets `Email address not authorized`. It is also rate
limited and carries no delivery guarantee, and Supabase states plainly that it is
not for production.

So email sign-up works for the team and fails for everyone else, which is the same
shape as phone sign-in working only for dashboard test numbers until Twilio is
connected. Configure custom SMTP (Resend, SES, Postmark, SendGrid) at
**Authentication → SMTP Settings**, then raise the rate limit, which starts at 30
messages per hour on a new sender.

Also check, in **Authentication → Sign In / Providers → Email**:

- **Confirm email** must be ON, or `sign_up()` returns a session immediately, no
  email is sent, and the confirm screen never appears.
- **Email OTP Expiration** is the code's lifetime. Every template tells the user one
  hour, so if you change it, change the copy in all six files to match.
- **Secure email change** should stay ON. It sends the change-email code to the old
  address as well as the new one, so losing access to an inbox is not by itself
  enough to take an account.

### Turning Confirm email ON affects accounts that already exist

Checked against production on 2026-08-03: **22 accounts, 20 with an email address,
15 with the address confirmed.** The other 5 have never confirmed. Switching Confirm
email on makes confirmation a precondition for those accounts, so decide what should
happen to them before flipping it — either confirm them from the dashboard, or
expect them to go through the code flow on next sign-in.
