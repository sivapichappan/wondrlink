/**
 * Forgot password — email in, code back, new password set. Three steps in one
 * screen, matching the shape of phone.tsx.
 *
 * By code rather than by reset link: a link opens a browser, which on a phone
 * means leaving the app and coming back, and the deep-link handling that would
 * make it seamless does not exist. The code keeps the whole thing in one place.
 *
 * The code only arrives if the Reset Password email template carries
 * {{ .Token }} — see config/email_templates/.
 *
 * Whether an address has an account is never revealed: step 1 always advances to
 * code entry, because branching on "no such account" would hand an attacker a
 * way to enumerate patient email addresses.
 */

import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import {
  passwordProblem,
  sendPasswordResetCode,
  setNewPassword,
  verifyPasswordResetCode,
} from '@/lib/api/auth';
import { extractErrorMessage } from '@/lib/api/client';

type Step = 'email' | 'code' | 'password';

const TITLES: Record<Step, string> = {
  email: 'Reset your password',
  code: 'Enter your code',
  password: 'Choose a new password',
};

export default function ForgotPassword() {
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const codeRef = useRef<TextInput>(null);

  const onSendCode = async () => {
    setError(null);
    if (!email.trim().includes('@')) {
      setError('Please enter the email address on your account.');
      return;
    }
    setBusy(true);
    try {
      await sendPasswordResetCode(email);
      setStep('code');
      setTimeout(() => codeRef.current?.focus(), 250);
    } catch (e) {
      setError(extractErrorMessage(e, 'We could not send a code. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  const onVerify = async () => {
    setError(null);
    if (code.trim().length < 6) {
      setError('Please enter the 6-digit code from the email.');
      return;
    }
    setBusy(true);
    try {
      await verifyPasswordResetCode(email, code);
      setStep('password');
    } catch (e) {
      setError(extractErrorMessage(e, 'That code did not work. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  const onSetPassword = async () => {
    setError(null);
    const weak = passwordProblem(password);
    if (weak) {
      setError(weak);
      return;
    }
    if (password !== confirm) {
      setError('Those two passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      await setNewPassword(password);
      setDone(true);
    } catch (e) {
      setError(extractErrorMessage(e, 'We could not save that password. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  // verifyPasswordResetCode leaves a real session behind, so the user is already
  // signed in at this point. Send them to login anyway: someone who just reset a
  // password expects to use it, and the root layout would otherwise drop them
  // into the app with no sign that anything changed.
  if (done) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
        <ScrollView
          contentContainerStyle={{
            padding: Spacing.xl,
            gap: Spacing.lg,
            flexGrow: 1,
            justifyContent: 'center',
          }}>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 26, color: Colors.textPrimary }}>
            Your password is saved
          </Text>
          <Text style={{ fontSize: FontSize.md, lineHeight: 21, color: Colors.textSecondary }}>
            You can sign in with your new password now.
          </Text>
          <Button
            label="Go to sign in"
            size="lg"
            fullWidth
            onPress={() => router.replace('/(auth)/login')}
          />
        </ScrollView>
      </SafeAreaView>
    );
  }

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
              {TITLES[step]}
            </Text>
            <Text style={{ fontSize: FontSize.md, lineHeight: 21, color: Colors.textSecondary }}>
              {step === 'email'
                ? 'Tell us your email address and we will send you a 6-digit code.'
                : step === 'code'
                  ? `We sent a code to ${email.trim()}. It can take a minute to arrive.`
                  : 'Pick something you have not used here before.'}
            </Text>
          </View>

          {step === 'email' ? (
            <TextField
              label="Email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              autoFocus
            />
          ) : step === 'code' ? (
            <TextField
              ref={codeRef}
              label="Code from the email"
              value={code}
              onChangeText={setCode}
              placeholder="123456"
              keyboardType="number-pad"
              textContentType="oneTimeCode"
              maxLength={8}
            />
          ) : (
            <>
              <TextField
                label="New password"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                autoComplete="new-password"
                hint="At least 8 characters, with a capital letter and a number."
                autoFocus
              />
              <TextField
                label="Confirm new password"
                value={confirm}
                onChangeText={setConfirm}
                secureTextEntry
                autoComplete="new-password"
                onSubmitEditing={onSetPassword}
                returnKeyType="go"
              />
            </>
          )}

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

          <View style={{ gap: Spacing.sm, marginTop: 'auto', paddingBottom: Spacing.lg }}>
            {step === 'email' ? (
              <Button
                label={busy ? 'Sending…' : 'Email me a code'}
                size="lg"
                fullWidth
                disabled={busy}
                onPress={onSendCode}
              />
            ) : step === 'code' ? (
              <>
                <Button
                  label={busy ? 'Checking…' : 'Continue'}
                  size="lg"
                  fullWidth
                  disabled={busy}
                  onPress={onVerify}
                />
                <Button
                  label="Send a new code"
                  variant="ghost"
                  fullWidth
                  disabled={busy}
                  onPress={() => {
                    setCode('');
                    setError(null);
                    setStep('email');
                  }}
                />
              </>
            ) : (
              <Button
                label={busy ? 'Saving…' : 'Save new password'}
                size="lg"
                fullWidth
                disabled={busy}
                onPress={onSetPassword}
              />
            )}
            {step !== 'password' ? (
              <Button
                label="Back to sign in"
                variant="ghost"
                fullWidth
                disabled={busy}
                onPress={() => router.replace('/(auth)/login')}
              />
            ) : null}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
