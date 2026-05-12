import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts } from '@/constants/theme';
import { register } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';

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
      const msg =
        e instanceof ApiError
          ? e.body?.error ?? `Registration failed (${e.status})`
          : 'Registration failed. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }}>
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
          />

          <Button label="Create account" fullWidth size="lg" loading={submitting} onPress={onSubmit} />
          <Button
            label="Already have an account? Log in"
            variant="ghost"
            fullWidth
            onPress={() => router.replace('/(auth)/login')}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
