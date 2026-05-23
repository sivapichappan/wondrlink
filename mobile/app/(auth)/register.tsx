import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts } from '@/constants/theme';
import { register } from '@/lib/api/auth';
import { ApiError, extractErrorMessage } from '@/lib/api/client';

export default function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      const fallback =
        e instanceof ApiError
          ? `Registration failed (${e.status})`
          : 'Registration failed. Please try again.';
      // extractErrorMessage handles object-shaped errors (e.g. Supabase
      // AuthError leaking through as { code, message }) so setError never
      // gets an object, which would crash <Text>{error}</Text>.
      const msg = e instanceof ApiError ? extractErrorMessage(e.body, fallback) : extractErrorMessage(e, fallback);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

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

        {/* Pinned action area — always visible above the keyboard */}
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
