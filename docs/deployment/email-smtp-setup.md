# Email / SMTP Setup for Supabase Auth

**Status:** REQUIRED before public launch
**Owner:** Supervisor + Eng
**Cost:** $0 to start (Resend free tier covers 3,000 emails/month and 100/day)

> Until this is done, signup verification emails go through Supabase's default sender (`noreply@mail.app.supabase.io`), which is heavily rate-limited (~4 emails/hour) and frequently silently blocked by Gmail / Outlook. This is fine for engineering testing but **not acceptable for any real user**.

---

## Why Resend (vs. SendGrid, Postmark, AWS SES)

- **Modern API + dashboard** — drop-in replacement for Supabase's default, no auth-flow rewrite
- **Generous free tier** — 3,000 emails/month, 100/day. We'd hit this around 1,000 monthly active users.
- **HIPAA-eligible plan** ($20/mo, signed BAA available) — matches our compliance posture
- **Domain verification is straightforward** — 3 DNS records on `wondrlinkfoundation.org`
- **Strong deliverability** by reputation; their abuse / suppression handling is conservative

If Foundation policy prefers an existing vendor (e.g. SendGrid because of an org-wide contract), the Supabase SMTP setup steps below are identical — only the provider-specific account creation differs.

---

## Setup steps (~30 min total)

### 1. Create a Resend account

- https://resend.com/signup
- Use the WondrLink Foundation org email (e.g. `info@wondrlinkfoundation.org`) so the account isn't tied to one person.
- Confirm the org's email.

### 2. Add and verify the sending domain

Resend → Domains → **Add Domain** → enter `wondrlinkfoundation.org`.

You'll see 3 DNS records to add:
- 1 × MX record (for return-path)
- 1 × TXT record (SPF)
- 1 × TXT record (DKIM)

Add these to whoever manages `wondrlinkfoundation.org` DNS (typically the Foundation's IT / domain registrar). Resend's docs walk through each major DNS provider.

DNS propagation typically completes in 5–60 minutes. The Resend dashboard updates each record's status from "pending" to "verified" automatically.

### 3. Create a Resend API key

Resend → API Keys → **Create API Key**:
- Name: `Supabase-Auth-Production`
- Permission: **Sending access** (least-privilege)
- Domain: restrict to `wondrlinkfoundation.org`
- Copy the key (only shown once) — save it temporarily for step 4.

### 4. Configure Supabase to use Resend SMTP

- https://supabase.com/dashboard/project/kgcelxfhmhymutyrorpw/settings/auth
- Scroll to **SMTP Settings** → click **Enable Custom SMTP**
- Fill in:

| Field | Value |
|---|---|
| Sender email | `noreply@wondrlinkfoundation.org` |
| Sender name | `WondrChat` |
| Host | `smtp.resend.com` |
| Port | `465` |
| Username | `resend` |
| Password | the Resend API key from step 3 |
| Minimum interval | `60` seconds (default) |

- Click **Save**

### 5. Customize the email templates (optional but recommended)

Same Supabase dashboard → **Authentication** → **Email Templates**.

For at minimum the "Confirm signup" template, replace the default Supabase boilerplate with WondrChat-branded copy:

```html
<h2>Welcome to WondrChat</h2>
<p>Thanks for signing up. Confirm your email address to start your conversations.</p>
<p>
  <a href="{{ .ConfirmationURL }}"
     style="display:inline-block;background:#1F5D4F;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600;">
    Confirm my email
  </a>
</p>
<p style="color:#6B7570;font-size:13px;">
  If the button doesn't work, paste this link into your browser:<br>
  <span style="color:#1F5D4F;">{{ .ConfirmationURL }}</span>
</p>
<p style="color:#6B7570;font-size:12px;margin-top:24px;">
  WondrChat is an educational support tool, not medical advice. If you didn't sign up
  for WondrChat, you can safely ignore this email.
</p>
```

Repeat for "Reset password" and "Magic link" templates as needed.

### 6. Test it end-to-end

- Mobile app → Sign up with a fresh email (e.g. `your-name+resend-test@gmail.com`)
- Expected: verification email arrives in your inbox within 30 seconds, branded as WondrChat, from `noreply@wondrlinkfoundation.org`
- Tap the link → mobile app should accept the now-confirmed account on next login

### 7. Re-enable email confirmation in Supabase

If you disabled it for the preview (see `docs/deployment/email-smtp-setup.md`#preview-unblock or supervisor convo), turn it back on:

- https://supabase.com/dashboard/project/kgcelxfhmhymutyrorpw/auth/providers → Email → toggle on **Confirm email** → Save.

---

## Deliverability hardening (after step 4 works)

- Set up **DMARC** alongside SPF + DKIM. Resend's docs link to a one-line TXT record template — adds another layer Gmail/Outlook respect.
- Add the sender email to Resend's **suppression list webhook** so we know when an address bounces/marks-as-spam → can mirror that into our Supabase records.
- Enable **Resend's bounce + complaint tracking** so we can debug delivery issues per-user without grep'ing logs.

## When to revisit

- Daily volume creeps above 80% of the 100/day free-tier cap → upgrade to Resend's $20/mo HIPAA-eligible plan + sign BAA.
- Monthly volume > 2,500 → same upgrade trigger.
- Any user-reported "didn't receive my email" → Resend dashboard shows per-email status (delivered, bounced, complained).

## Companion documents

- [docs/deployment/environments.md](environments.md) — Staging/Production split that this SMTP config will mirror
- [docs/compliance/subprocessor_chain.md](../compliance/subprocessor_chain.md) — Add Resend as a sub-processor + DPA target once SMTP is live (requires a one-line entry update)
- [docs/compliance/dpia.md](../compliance/dpia.md) — Update the data-flow diagram to include Resend as an email-delivery sub-processor
