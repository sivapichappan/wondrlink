/**
 * Phone sign-in (Sage doc screen 1) — number in, code back, no password.
 * Two steps in one screen. First-time numbers become accounts at verify.
 * Email login remains available from Welcome as the fallback path.
 */

import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { sendPhoneCode, verifyPhoneCode } from '@/lib/api/auth';
import { ApiError, extractErrorMessage } from '@/lib/api/client';

export default function PhoneSignIn() {
  const [step, setStep] = useState<'phone' | 'code'>('phone');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const codeRef = useRef<TextInput>(null);
  const qc = useQueryClient();

  const fail = (e: unknown, fallback: string) => {
    const msg =
      e instanceof ApiError ? extractErrorMessage(e.body, fallback) : extractErrorMessage(e, fallback);
    setError(msg);
  };

  const onSend = async () => {
    setError(null);
    if (phone.replace(/\D/g, '').length < 10) {
      setError('Please enter your full phone number.');
      return;
    }
    setBusy(true);
    try {
      await sendPhoneCode(phone);
      setStep('code');
      setTimeout(() => codeRef.current?.focus(), 250);
    } catch (e) {
      fail(e, 'We could not send a code. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const onVerify = async () => {
    setError(null);
    if (code.trim().length < 4) {
      setError('Please enter the code from the text message.');
      return;
    }
    setBusy(true);
    try {
      await verifyPhoneCode(phone, code);
      // Root layout detects the new session and routes onward.
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
    } catch (e) {
      fail(e, 'That code did not work. Please try again.');
    } finally {
      setBusy(false);
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
              {step === 'phone' ? 'Your phone number' : 'Enter your code'}
            </Text>
            <Text style={{ fontSize: FontSize.md, lineHeight: 21, color: Colors.textSecondary }}>
              {step === 'phone'
                ? 'No password and no email. We text you a code to sign in.'
                : `We sent a code to ${phone.trim()}. It may take a few seconds to arrive.`}
            </Text>
          </View>

          {step === 'phone' ? (
            <TextField
              label="Phone number"
              value={phone}
              onChangeText={setPhone}
              placeholder="(555) 000-0000"
              keyboardType="phone-pad"
              textContentType="telephoneNumber"
              autoFocus
            />
          ) : (
            <TextField
              ref={codeRef}
              label="Code from the text message"
              value={code}
              onChangeText={setCode}
              placeholder="123456"
              keyboardType="number-pad"
              textContentType="oneTimeCode"
              maxLength={8}
            />
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
            {step === 'phone' ? (
              <Button label={busy ? 'Sending…' : 'Text me a code'} size="lg" fullWidth disabled={busy} onPress={onSend} />
            ) : (
              <>
                <Button label={busy ? 'Checking…' : 'Sign in'} size="lg" fullWidth disabled={busy} onPress={onVerify} />
                <Button
                  label="Send a new code"
                  variant="ghost"
                  fullWidth
                  disabled={busy}
                  onPress={() => {
                    setCode('');
                    setStep('phone');
                  }}
                />
              </>
            )}
            <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, textAlign: 'center' }}>
              Message and data rates may apply. Private and encrypted.
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
