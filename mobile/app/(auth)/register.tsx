import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import {
  NoSessionError,
  passwordProblem,
  register,
  resendSignupConfirmation,
  verifySignupCode,
} from '@/lib/api/auth';
import { ApiError, extractErrorMessage } from '@/lib/api/client';

export default function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verifyEmail, setVerifyEmail] = useState<string | null>(null);
  const qc = useQueryClient();

  const onSubmit = async () => {
    setError(null);
    if (!email.trim()) {
      setError('Email is required.');
      return;
    }
    // Same rules the server enforces, checked here so a weak password does not
    // cost a round trip.
    const weak = passwordProblem(password);
    if (weak) {
      setError(weak);
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setSubmitting(true);
    try {
      await register(email, password);
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      // Root layout will route to onboarding.
    } catch (e) {
      // NoSessionError = sign-up succeeded but Supabase has email confirmation
      // enabled, so there is no session yet. That is the normal path, not an
      // error: move to code entry rather than showing red text.
      if (e instanceof NoSessionError) {
        setVerifyEmail(email.trim());
        return;
      }
      const fallback =
        e instanceof ApiError
          ? `Registration failed (${e.status})`
          : 'Registration failed. Please try again.';
      const msg = e instanceof ApiError ? extractErrorMessage(e.body, fallback) : extractErrorMessage(e, fallback);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Account created, email not confirmed yet: collect the code.
  if (verifyEmail) {
    return <ConfirmCodeScreen email={verifyEmail} onUseDifferent={() => setVerifyEmail(null)} />;
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}>
        {/* Scrollable form fields */}
        <ScrollView
          contentContainerStyle={{ padding: 24, gap: 16, flexGrow: 1 }}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive">
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 24, color: Colors.textPrimary }}>
            Create your account
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>
            You'll be asked a few consent questions on the next screen before you can start
            chatting.
          </Text>

          <TextField
            label="Email"
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />
          <TextField
            label="Password"
            secureTextEntry
            autoComplete="new-password"
            value={password}
            onChangeText={setPassword}
            hint="At least 8 characters, with a capital letter and a number."
          />
          <TextField
            label="Confirm password"
            secureTextEntry
            autoComplete="new-password"
            value={confirm}
            onChangeText={setConfirm}
            error={error ?? undefined}
            onSubmitEditing={onSubmit}
            returnKeyType="go"
          />
        </ScrollView>

        {/* Pinned action area, always visible above the keyboard */}
        <View
          style={{
            padding: 16,
            paddingBottom: Platform.OS === 'ios' ? 24 : 16,
            borderTopWidth: 1,
            borderTopColor: Colors.border,
            backgroundColor: Colors.surface,
            gap: 8,
          }}>
          <Button
            label="Create account"
            fullWidth
            size="lg"
            loading={submitting}
            onPress={onSubmit}
          />
          <Button
            label="Already have an account? Log in"
            variant="ghost"
            fullWidth
            onPress={() => router.replace('/(auth)/login')}
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

/**
 * Sign-up step 2: confirm the six-digit code from the email.
 *
 * Replaces the old "check your email for a link" dead-end, which asked the user
 * to leave the app, tap a link, come back, and sign in again. The code keeps
 * them in one place and lands them straight in a session, so onboarding follows
 * immediately.
 *
 * The code only arrives if the Confirm signup email template carries
 * {{ .Token }} — see config/email_templates/.
 */
function ConfirmCodeScreen({
  email,
  onUseDifferent,
}: {
  email: string;
  onUseDifferent: () => void;
}) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const [resendNote, setResendNote] = useState<string | null>(null);
  const qc = useQueryClient();

  const onVerify = async () => {
    setError(null);
    if (code.trim().length < 6) {
      setError('Please enter the 6-digit code from the email.');
      return;
    }
    setBusy(true);
    try {
      await verifySignupCode(email, code);
      // Root layout sees the new session and routes on to consent.
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
    } catch (e) {
      setError(extractErrorMessage(e, 'That code did not work. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  const doResend = async () => {
    setResending(true);
    setResendNote(null);
    setError(null);
    try {
      await resendSignupConfirmation(email);
      setResendNote('We sent another code. It can take a minute to arrive.');
    } catch (e) {
      // Supabase rate-limits resends hard. Either way the user needs the same
      // instruction, so the note never reveals whether the account exists.
      const msg = e && typeof e === 'object' && 'message' in e ? String((e as Error).message) : '';
      setResendNote(
        /rate|too many|wait|security purposes/i.test(msg)
          ? 'Please wait a minute before asking for another code.'
          : 'We tried again. If nothing arrives in a few minutes, check your spam folder.',
      );
    } finally {
      setResending(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={{ padding: Spacing.xl, gap: Spacing.lg, flexGrow: 1 }}
          keyboardShouldPersistTaps="handled">
          <View style={{ gap: 6, marginTop: Spacing.xl }}>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: 26, color: Colors.textPrimary }}>
              Confirm your email
            </Text>
            <Text style={{ fontSize: FontSize.md, lineHeight: 21, color: Colors.textSecondary }}>
              We sent a 6-digit code to {email}. Enter it below to finish setting up your account.
            </Text>
          </View>

          <TextField
            label="Code from the email"
            value={code}
            onChangeText={setCode}
            placeholder="123456"
            keyboardType="number-pad"
            textContentType="oneTimeCode"
            maxLength={8}
            autoFocus
          />

          {error ? (
            <View
              style={{
                backgroundColor: Colors.warningBg,
                borderRadius: Radius.md,
                padding: Spacing.md,
              }}>
              <Text style={{ color: Colors.textPrimary, fontSize: FontSize.base, lineHeight: 19 }}>
                {error}
              </Text>
            </View>
          ) : null}

          {resendNote ? (
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.xs, lineHeight: 17 }}>
              {resendNote}
            </Text>
          ) : null}

          <View style={{ gap: Spacing.sm, marginTop: 'auto', paddingBottom: Spacing.lg }}>
            <Button
              label={busy ? 'Checking…' : 'Confirm and continue'}
              size="lg"
              fullWidth
              disabled={busy}
              onPress={onVerify}
            />
            <Button
              label="Send a new code"
              variant="secondary"
              fullWidth
              loading={resending}
              disabled={busy}
              onPress={doResend}
            />
            <Button
              label="Use a different email"
              variant="ghost"
              fullWidth
              disabled={busy}
              onPress={onUseDifferent}
            />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
