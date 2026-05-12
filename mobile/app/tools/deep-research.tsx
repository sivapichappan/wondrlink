import { Stack, router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MarkdownText } from '@/components/chat/MarkdownText';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { deepResearch } from '@/lib/api/tools';
import type { DeepResearchResponse } from '@shared/types';

export default function DeepResearchScreen() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<DeepResearchResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (query.trim().length < 8) {
      setError('Please ask a more detailed question.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await deepResearch(query.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.body?.error ?? 'Could not run deep research.' : 'Could not run deep research.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Deep research', headerBackTitle: 'Tools' }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            Deep research runs a longer, multi-pass search across the medical guideline library.
            It typically takes 15–45 seconds. Limited to 3 requests per 5 minutes.
          </Text>

          <TextField
            label="Your research question"
            multiline
            placeholder="e.g. How do I weigh FOLFOX vs FOLFIRI for stage III colon cancer?"
            value={query}
            onChangeText={setQuery}
            style={{ minHeight: 100, paddingTop: 12, textAlignVertical: 'top' }}
            error={error ?? undefined}
          />

          <Button
            label={submitting ? 'Researching…' : 'Start deep research'}
            fullWidth
            size="lg"
            loading={submitting}
            onPress={submit}
          />

          {result && result.status === 'off_topic' && (
            <View
              style={{
                padding: 12,
                borderRadius: Radius.md,
                backgroundColor: Colors.warningBg,
              }}>
              <Text style={{ color: Colors.warning, fontSize: 13, lineHeight: 19 }}>
                {result.report}
              </Text>
            </View>
          )}

          {result && result.status === 'ok' && (
            <View style={{ gap: 10 }}>
              {result.sections?.length > 0 ? (
                result.sections.map((s, i) => (
                  <View
                    key={i}
                    style={{
                      padding: 14,
                      borderRadius: Radius.md,
                      borderWidth: 1,
                      borderColor: Colors.border,
                      backgroundColor: Colors.surface,
                    }}>
                    <Text
                      style={{
                        fontFamily: Fonts.sansSemiBold,
                        fontSize: 14,
                        color: Colors.textPrimary,
                        marginBottom: 6,
                      }}>
                      {s.title}
                    </Text>
                    <MarkdownText>{s.body}</MarkdownText>
                  </View>
                ))
              ) : (
                <MarkdownText>{result.report}</MarkdownText>
              )}
            </View>
          )}

          <Button label="Back to tools" variant="ghost" fullWidth onPress={() => router.back()} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
