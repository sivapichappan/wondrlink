import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts } from '@/constants/theme';
import { login } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  const onSubmit = async () => {
    setError(null);
    if (!email.trim() || !password) {
      setError('Email and password are required.');
      return;
    }
    setSubmitting(true);
    try {
      await login(email, password);
      // Invalidate so the root layout re-reads acknowledgement state.
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      // Root layout will detect the new session and route.
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.body?.error ?? `Login failed (${e.status})`
          : 'Login failed. Please try again.';
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
            Welcome back
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>
            Sign in to continue your WondrChat conversations.
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
            autoComplete="password"
            value={password}
            onChangeText={setPassword}
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
          <Button label="Log in" fullWidth size="lg" loading={submitting} onPress={onSubmit} />
          <Button
            label="Don't have an account? Create one"
            variant="ghost"
            fullWidth
            onPress={() => router.replace('/(auth)/register')}
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
