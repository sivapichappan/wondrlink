# Auth email templates

Two Supabase auth emails, kept in the repo because they are **patient-facing copy**
and because the app depends on their contents.

| File | Supabase template | Sent by | Confirmed with |
|---|---|---|---|
| `confirm_signup.html` | Confirm signup | `sign_up()` (Flask `/api/auth/register`) | `verifyOtp(type: 'signup')` |
| `reset_password.html` | Reset Password | `resetPasswordForEmail()` | `verifyOtp(type: 'recovery')` |

## The one thing that must not change

`{{ .Token }}` is what makes these **codes** instead of **links**. Supabase decides
between the two purely on what the template contains:

- `{{ .ConfirmationURL }}` → a link the user taps in a browser
- `{{ .Token }}` → a six digit code

Both app screens ask for a code. Swap a template back to the link version and the
user gets an email with nothing in it they can type. `tests/test_email_templates.py`
fails if that happens.

## Applying them (dashboard, one time each)

1. Supabase dashboard → **Authentication → Emails**
2. Pick the template, paste the file's contents into the body
3. Subjects: `Your Sage code` and `Your Sage reset code`
4. Save

The HTML deliberately uses tables and inline styles. Email clients drop `<style>`
blocks and most modern CSS, and Outlook needs the table.

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
- **Email OTP Expiration** is the code's lifetime. Both templates tell the user
  one hour, so if you change it, change the copy in both files to match.
