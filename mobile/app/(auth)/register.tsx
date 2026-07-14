import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts } from '@/constants/theme';
import { NoSessionError, register, resendSignupConfirmation } from '@/lib/api/auth';
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
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
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
      // NoSessionError = sign-up succeeded but Supabase has email
      // confirmation enabled, so there's no session yet. This is a
      // success path, not an error, surface as an info/success banner
      // with a clear "Go to Log In" CTA, not red error text.
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

  // If we're in the "check your email" state, render a dedicated success
  // screen instead of the form.
  if (verifyEmail) {
    return <VerifyEmailScreen email={verifyEmail} onUseDifferent={() => setVerifyEmail(null)} />;
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
            hint="At least 8 characters."
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
 * "Check your email" screen rendered after a sign-up that returned a
 * NoSessionError (Supabase has email confirmation enabled).
 *
 * Surfaces a clear next step + a Resend button (Supabase rate-limits
 * the resend aggressively, so we show a generic "we tried again"
 * message regardless of result, never reveal whether the account
 * exists).
 */
function VerifyEmailScreen({
  email,
  onUseDifferent,
}: {
  email: string;
  onUseDifferent: () => void;
}) {
  const [resending, setResending] = useState(false);
  const [resendNote, setResendNote] = useState<string | null>(null);

  const doResend = async () => {
    setResending(true);
    setResendNote(null);
    try {
      await resendSignupConfirmation(email);
      setResendNote("We've sent another verification email. Check your inbox (and spam).");
    } catch (e) {
      // Supabase often rate-limits, show a generic message either way.
      // Real failures still surface so we can debug.
      const isRateLimit =
        e && typeof e === 'object' && 'message' in e &&
        typeof (e as any).message === 'string' &&
        /rate|too many|wait/i.test((e as any).message);
      setResendNote(
        isRateLimit
          ? "Please wait a minute before requesting another email, Supabase rate-limits these."
          : "We tried to resend. If you still don't see the email in a few minutes, check spam or use a different address."
      );
    } finally {
      setResending(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 24, gap: 16, flexGrow: 1, justifyContent: 'center' }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 24, color: Colors.textPrimary, textAlign: 'center' }}>
          Check your email
        </Text>
        <View
          style={{
            padding: 16,
            borderRadius: 12,
            backgroundColor: Colors.sidebarBg,
            borderWidth: 1,
            borderColor: Colors.primary,
          }}>
          <Text style={{ color: Colors.textPrimary, fontSize: 14, lineHeight: 21 }}>
            We sent a verification link to{' '}
            <Text style={{ fontFamily: Fonts.sansSemiBold }}>{email}</Text>. Tap the link in that
            email, then come back here and sign in.
          </Text>
        </View>
        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19, textAlign: 'center' }}>
          Don't see the email? Check your spam folder, your Gmail "Promotions" tab, or use the
          resend button below.
        </Text>
        {resendNote && (
          <Text
            style={{
              color: Colors.textSecondary,
              fontSize: 12,
              lineHeight: 17,
              textAlign: 'center',
              fontStyle: 'italic',
            }}>
            {resendNote}
          </Text>
        )}
      </ScrollView>
      <View
        style={{
          padding: 16,
          paddingBottom: Platform.OS === 'ios' ? 24 : 16,
          borderTopWidth: 1,
          borderTopColor: Colors.border,
          backgroundColor: Colors.surface,
          gap: 8,
        }}>
        <Button label="Go to Log In" fullWidth size="lg" onPress={() => router.replace('/(auth)/login')} />
        <Button
          label="Resend verification email"
          variant="secondary"
          fullWidth
          loading={resending}
          onPress={doResend}
        />
        <Button label="Use a different email" variant="ghost" fullWidth onPress={onUseDifferent} />
      </View>
    </SafeAreaView>
  );
}
