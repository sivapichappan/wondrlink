import { Stack, router } from 'expo-router';
import { Phone } from 'lucide-react-native';
import { useState } from 'react';
import {
  Alert,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { saveScreening } from '@/lib/api/tools';
import type { ScreeningCrisisResources } from '@shared/types';

const PHQ9_QUESTIONS = [
  'Little interest or pleasure in doing things',
  'Feeling down, depressed, or hopeless',
  'Trouble falling or staying asleep, or sleeping too much',
  'Feeling tired or having little energy',
  'Poor appetite or overeating',
  'Feeling bad about yourself — or that you are a failure or have let yourself or your family down',
  'Trouble concentrating on things, such as reading the newspaper or watching television',
  'Moving or speaking so slowly that other people could have noticed; or the opposite — being so fidgety or restless that you have been moving around a lot more than usual',
  'Thoughts that you would be better off dead, or of hurting yourself in some way',
];

const SCALE = [
  { value: 0, label: 'Not at all' },
  { value: 1, label: 'Several days' },
  { value: 2, label: 'More than half the days' },
  { value: 3, label: 'Nearly every day' },
];

function severityLabel(total: number): string {
  if (total <= 4) return 'Minimal';
  if (total <= 9) return 'Mild';
  if (total <= 14) return 'Moderate';
  if (total <= 19) return 'Moderately severe';
  return 'Severe';
}

export default function PHQ9Screen() {
  const [answers, setAnswers] = useState<(number | null)[]>(Array(9).fill(null));
  const [submitting, setSubmitting] = useState(false);
  const [resultScore, setResultScore] = useState<number | null>(null);
  const [crisis, setCrisis] = useState<ScreeningCrisisResources | null>(null);

  const allAnswered = answers.every((a) => a !== null);
  const total = answers.reduce((acc: number, a) => acc + (a ?? 0), 0);

  const submit = async () => {
    if (!allAnswered) return;
    setSubmitting(true);
    try {
      const scores: Record<string, number> = {};
      answers.forEach((a, i) => {
        scores[`q${i + 1}`] = a ?? 0;
      });
      const res = await saveScreening({
        instrument: 'PHQ9',
        scores,
        total_score: total,
        severity_label: severityLabel(total),
      });
      setResultScore(res.total_score);
      if (res.is_crisis && res.crisis_resources) {
        setCrisis(res.crisis_resources);
      }
    } catch {
      Alert.alert('Could not save', 'Please check your connection and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'PHQ-9 check-in', headerBackTitle: 'Tools' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 20 }}>
        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
          Over the last 2 weeks, how often have you been bothered by any of the following problems?
        </Text>

        {PHQ9_QUESTIONS.map((q, i) => (
          <View key={i} style={{ gap: 8 }}>
            <Text
              style={{
                color: Colors.textPrimary,
                fontFamily: Fonts.sansMedium,
                fontSize: 14,
                lineHeight: 20,
              }}>
              {i + 1}. {q}
            </Text>
            <View style={{ gap: 6 }}>
              {SCALE.map((opt) => {
                const selected = answers[i] === opt.value;
                return (
                  <Pressable
                    key={opt.value}
                    onPress={() => {
                      const next = [...answers];
                      next[i] = opt.value;
                      setAnswers(next);
                    }}
                    accessibilityRole="radio"
                    accessibilityState={{ selected }}
                    style={({ pressed }) => ({
                      paddingHorizontal: 12,
                      paddingVertical: 10,
                      borderRadius: Radius.sm,
                      borderWidth: 1,
                      borderColor: selected ? Colors.primary : Colors.border,
                      backgroundColor: selected
                        ? Colors.sidebarBg
                        : pressed
                          ? Colors.surfaceMuted
                          : Colors.surface,
                    })}>
                    <Text
                      style={{
                        color: selected ? Colors.primary : Colors.textPrimary,
                        fontFamily: selected ? Fonts.sansSemiBold : Fonts.sans,
                        fontSize: 13,
                      }}>
                      {opt.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        ))}

        {resultScore !== null && (
          <View
            style={{
              backgroundColor: Colors.sidebarBg,
              padding: 14,
              borderRadius: Radius.md,
            }}>
            <Text
              style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
              Score: {resultScore} — {severityLabel(resultScore)}
            </Text>
            <Text style={{ color: Colors.textSecondary, fontSize: 12, marginTop: 4 }}>
              Saved to your Care snapshot. This is an informational tool, not a diagnosis.
            </Text>
          </View>
        )}

        <Button
          label={submitting ? 'Saving…' : 'Submit'}
          fullWidth
          size="lg"
          loading={submitting}
          disabled={!allAnswered}
          onPress={submit}
        />
        <Button
          label="Back to tools"
          variant="ghost"
          fullWidth
          onPress={() => router.back()}
        />
      </ScrollView>

      <CrisisModal resources={crisis} onClose={() => setCrisis(null)} />
    </SafeAreaView>
  );
}

function CrisisModal({
  resources,
  onClose,
}: {
  resources: ScreeningCrisisResources | null;
  onClose: () => void;
}) {
  if (!resources) return null;
  return (
    <Modal visible animationType="fade" transparent onRequestClose={onClose}>
      <View
        style={{
          flex: 1,
          backgroundColor: 'rgba(15,32,28,0.55)',
          justifyContent: 'center',
          padding: 20,
        }}>
        <View
          style={{
            backgroundColor: Colors.surface,
            borderRadius: Radius.lg,
            padding: 20,
            gap: 12,
          }}>
          <Text
            style={{ fontFamily: Fonts.serifBold, fontSize: 19, color: Colors.textPrimary }}>
            We're here for you
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
            {resources.message}
          </Text>
          <View style={{ gap: 8 }}>
            {resources.resources.map((r) => {
              const phoneMatch = r.contact.match(/(\d{3}[- ]?\d{3}[- ]?\d{4}|988|911)/);
              const phone = phoneMatch ? phoneMatch[0].replace(/[^0-9]/g, '') : null;
              return (
                <Pressable
                  key={r.name}
                  onPress={() => phone && Linking.openURL(`tel:${phone}`).catch(() => {})}
                  accessibilityRole={phone ? 'button' : undefined}
                  style={({ pressed }) => ({
                    flexDirection: 'row',
                    gap: 10,
                    alignItems: 'center',
                    padding: 12,
                    borderRadius: Radius.md,
                    backgroundColor: pressed ? Colors.sidebarBg : Colors.surfaceMuted,
                  })}>
                  {phone && <Phone size={16} color={Colors.primary} />}
                  <View style={{ flex: 1 }}>
                    <Text
                      style={{
                        color: Colors.textPrimary,
                        fontFamily: Fonts.sansSemiBold,
                        fontSize: 13,
                      }}>
                      {r.name}
                    </Text>
                    <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>{r.contact}</Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
          <Button label="Close" variant="secondary" fullWidth onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}
