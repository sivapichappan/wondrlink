import { Stack, router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { generatePreVisitQuestions } from '@/lib/api/tools';
import type { PreVisitGroup } from '@shared/types';

export default function PreVisitScreen() {
  const [context, setContext] = useState('');
  const [groups, setGroups] = useState<PreVisitGroup[] | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await generatePreVisitQuestions({ context: context.trim() || undefined });
      setGroups(res.groups || []);
    } catch (e) {
      setError(e instanceof ApiError ? e.body?.error ?? 'Could not generate' : 'Could not generate');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Pre-visit questions', headerBackTitle: 'Tools' }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            Optional: share anything specific you want to discuss at your next visit (symptoms,
            decisions, side effects). Sage will tailor the question list.
          </Text>

          <TextField
            label="What's on your mind? (optional)"
            multiline
            placeholder="e.g. I'm starting cycle 3 next week and dealing with neuropathy"
            value={context}
            onChangeText={setContext}
            style={{
              minHeight: 100,
              paddingTop: 12,
              textAlignVertical: 'top',
            }}
          />

          <Button
            label={submitting ? 'Generating…' : 'Generate questions'}
            fullWidth
            size="lg"
            loading={submitting}
            onPress={submit}
          />

          {error && <Text style={{ color: Colors.danger, fontSize: 13 }}>{error}</Text>}

          {groups &&
            groups.map((g, gi) => (
              <View key={`${gi}-${g.topic}`} style={{ gap: 8 }}>
                <Text
                  style={{
                    fontFamily: Fonts.sansSemiBold,
                    fontSize: 13,
                    color: Colors.primary,
                    letterSpacing: 0.3,
                  }}>
                  {g.topic.toUpperCase()}
                </Text>
                <View
                  style={{
                    backgroundColor: Colors.surface,
                    borderWidth: 1,
                    borderColor: Colors.border,
                    borderRadius: Radius.md,
                    padding: 12,
                    gap: 8,
                  }}>
                  {g.questions.map((q, qi) => (
                    <Text
                      key={qi}
                      style={{
                        color: Colors.textPrimary,
                        fontSize: 13,
                        lineHeight: 19,
                      }}>
                      • {q}
                    </Text>
                  ))}
                </View>
              </View>
            ))}

          <Button label="Back to tools" variant="ghost" fullWidth onPress={() => router.back()} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
