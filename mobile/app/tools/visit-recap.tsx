import { useQueryClient } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { ChevronDown, ChevronRight, Lock, Mic, Square } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useProfile } from '@/hooks/useCare';
import { useSpeechDictation } from '@/hooks/useSpeechDictation';
import { ApiError } from '@/lib/api/client';
import { generateVisitRecap } from '@/lib/api/tools';
import type { VisitRecapEntry, VisitRecapStructured } from '@shared/types';

function formatTimer(s: number): string {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function formatStamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Saved visit';
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function VisitRecapScreen() {
  const dict = useSpeechDictation();
  const profile = useProfile();
  const qc = useQueryClient();

  const [recap, setRecap] = useState<VisitRecapStructured | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(null);

  const transcript = dict.transcript;

  // Recording timer.
  useEffect(() => {
    if (!dict.recording) return;
    setSeconds(0);
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [dict.recording]);

  const history = ((profile.data?.profile?.visit_recaps as VisitRecapEntry[] | undefined) ?? [])
    .slice()
    .reverse();

  const submit = async () => {
    if (dict.recording) dict.stop();
    if (transcript.trim().length < 50) {
      setError('Please record or type at least a few sentences about your visit.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await generateVisitRecap({ transcript: transcript.trim() });
      setRecap(res.recap);
      // Refresh the saved-history list (the server appended this recap).
      qc.invalidateQueries({ queryKey: ['profile'] });
    } catch (e) {
      setError(
        e instanceof ApiError ? e.body?.error ?? 'Could not build a recap.' : 'Could not build a recap.',
      );
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
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }} keyboardShouldPersistTaps="handled">
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            Record your appointment as it happens, or type notes from what you remember. Sage
            organizes it into discussion points, treatment changes, and action items, and keeps a
            history so you can look back.
          </Text>

          {/* Record control */}
          {dict.recording ? (
            <Button
              label={`Stop recording · ${formatTimer(seconds)}`}
              variant="danger"
              fullWidth
              size="lg"
              leadingIcon={<Square size={16} color={Colors.surface} fill={Colors.surface} />}
              onPress={dict.stop}
            />
          ) : (
            <Button
              label={transcript.trim() ? 'Resume recording' : 'Record appointment'}
              variant="secondary"
              fullWidth
              size="lg"
              leadingIcon={<Mic size={18} color={Colors.primary} />}
              onPress={() => dict.start(transcript)}
            />
          )}

          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Lock size={12} color={Colors.textMuted} />
            <Text style={{ flex: 1, color: Colors.textMuted, fontSize: 11, lineHeight: 16 }}>
              Transcription happens on your device. The audio is never recorded to a file or
              uploaded.
            </Text>
          </View>

          <TextField
            label="Transcript / notes (50+ characters)"
            multiline
            editable={!dict.recording}
            placeholder="Tap record above, or type what you discussed: new instructions, side effects, treatment changes…"
            value={transcript}
            onChangeText={dict.edit}
            style={{ minHeight: 160, paddingTop: 12, textAlignVertical: 'top' }}
            error={error ?? undefined}
          />

          <Button
            label={submitting ? 'Building recap…' : 'Build recap'}
            fullWidth
            size="lg"
            loading={submitting}
            disabled={dict.recording}
            onPress={submit}
          />

          {recap && (
            <View style={{ gap: 12 }}>
              <RecapList title="Discussed" items={recap.discussed} />
              <RecapList title="Treatment changes" items={recap.treatment_changes} />
              <RecapList title="Action items" items={recap.action_items} />
              <RecapList title="Follow-up questions" items={recap.follow_up_questions} />
              {recap.flags?.length > 0 && <FlagsCard flags={recap.flags} />}
            </View>
          )}

          {/* History */}
          {history.length > 0 && (
            <View style={{ gap: 8, marginTop: 4 }}>
              <Text
                style={{ fontFamily: Fonts.sansSemiBold, fontSize: 15, color: Colors.textPrimary }}>
                Past visits
              </Text>
              {history.map((entry, i) => {
                const open = expanded === i;
                return (
                  <View
                    key={`${entry.timestamp}-${i}`}
                    style={{
                      borderWidth: 1,
                      borderColor: Colors.border,
                      borderRadius: Radius.md,
                      overflow: 'hidden',
                      backgroundColor: Colors.surface,
                    }}>
                    <Pressable
                      onPress={() => setExpanded(open ? null : i)}
                      accessibilityRole="button"
                      accessibilityLabel={`Visit from ${formatStamp(entry.timestamp)}`}
                      style={({ pressed }) => ({
                        backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
                      })}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', padding: 12 }}>
                        <View style={{ flex: 1, minWidth: 0 }}>
                          <Text
                            style={{
                              color: Colors.textPrimary,
                              fontFamily: Fonts.sansSemiBold,
                              fontSize: 13,
                            }}>
                            {formatStamp(entry.timestamp)}
                          </Text>
                          <Text
                            numberOfLines={open ? undefined : 1}
                            style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
                            {entry.transcript_preview}
                          </Text>
                        </View>
                        {open ? (
                          <ChevronDown size={18} color={Colors.primary} style={{ marginLeft: 8 }} />
                        ) : (
                          <ChevronRight size={18} color={Colors.primary} style={{ marginLeft: 8 }} />
                        )}
                      </View>
                    </Pressable>
                    {open && (
                      <View style={{ paddingHorizontal: 12, paddingBottom: 12, gap: 10 }}>
                        <RecapList title="Discussed" items={entry.recap.discussed} />
                        <RecapList title="Treatment changes" items={entry.recap.treatment_changes} />
                        <RecapList title="Action items" items={entry.recap.action_items} />
                        <RecapList
                          title="Follow-up questions"
                          items={entry.recap.follow_up_questions}
                        />
                        {entry.recap.flags?.length > 0 && <FlagsCard flags={entry.recap.flags} />}
                      </View>
                    )}
                  </View>
                );
              })}
            </View>
          )}

          <Button label="Back to tools" variant="ghost" fullWidth onPress={() => router.back()} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function FlagsCard({ flags }: { flags: string[] }) {
  return (
    <View
      style={{
        padding: 12,
        borderRadius: Radius.md,
        backgroundColor: Colors.emergencyBg,
        borderWidth: 1,
        borderColor: Colors.danger,
      }}>
      <Text style={{ color: Colors.danger, fontFamily: Fonts.sansSemiBold, fontSize: 13 }}>
        Things to double-check with your team
      </Text>
      {flags.map((f, i) => (
        <Text key={i} style={{ color: Colors.textPrimary, fontSize: 13, marginTop: 4 }}>
          • {f}
        </Text>
      ))}
    </View>
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
