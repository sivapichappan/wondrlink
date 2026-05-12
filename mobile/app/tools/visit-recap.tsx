import { Stack, router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { generateVisitRecap } from '@/lib/api/tools';
import type { VisitRecapStructured } from '@shared/types';

export default function VisitRecapScreen() {
  const [transcript, setTranscript] = useState('');
  const [recap, setRecap] = useState<VisitRecapStructured | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (transcript.trim().length < 50) {
      setError('Please share at least a few sentences about your visit.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await generateVisitRecap({ transcript: transcript.trim() });
      setRecap(res.recap);
    } catch (e) {
      setError(e instanceof ApiError ? e.body?.error ?? 'Could not build a recap.' : 'Could not build a recap.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Visit recap', headerBackTitle: 'Tools' }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            Paste or type freeform notes from your visit (or what you remember). WondrChat will
            organize them into discussion points, treatment changes, and action items.
          </Text>

          <TextField
            label="Visit notes (50+ characters)"
            multiline
            placeholder="What did you discuss? Any new instructions, side effects, treatment changes?"
            value={transcript}
            onChangeText={setTranscript}
            style={{ minHeight: 160, paddingTop: 12, textAlignVertical: 'top' }}
            error={error ?? undefined}
          />

          <Button
            label={submitting ? 'Building recap…' : 'Build recap'}
            fullWidth
            size="lg"
            loading={submitting}
            onPress={submit}
          />

          {recap && (
            <View style={{ gap: 12 }}>
              <RecapList title="Discussed" items={recap.discussed} />
              <RecapList title="Treatment changes" items={recap.treatment_changes} />
              <RecapList title="Action items" items={recap.action_items} />
              <RecapList title="Follow-up questions" items={recap.follow_up_questions} />
              {recap.flags?.length > 0 && (
                <View
                  style={{
                    padding: 12,
                    borderRadius: Radius.md,
                    backgroundColor: '#FFEDEC',
                    borderWidth: 1,
                    borderColor: Colors.danger,
                  }}>
                  <Text
                    style={{ color: Colors.danger, fontFamily: Fonts.sansSemiBold, fontSize: 13 }}>
                    Things to double-check with your team
                  </Text>
                  {recap.flags.map((f, i) => (
                    <Text key={i} style={{ color: Colors.textPrimary, fontSize: 13, marginTop: 4 }}>
                      • {f}
                    </Text>
                  ))}
                </View>
              )}
            </View>
          )}

          <Button label="Back to tools" variant="ghost" fullWidth onPress={() => router.back()} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function RecapList({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <View
      style={{
        padding: 12,
        borderRadius: Radius.md,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.surface,
      }}>
      <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 13, color: Colors.textPrimary }}>
        {title}
      </Text>
      <View style={{ marginTop: 6, gap: 4 }}>
        {items.map((it, i) => (
          <Text key={i} style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            • {it}
          </Text>
        ))}
      </View>
    </View>
  );
}
