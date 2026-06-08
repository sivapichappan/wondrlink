import { Stack, router } from 'expo-router';
import { ThumbsDown, ThumbsUp } from 'lucide-react-native';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { submitFeedback } from '@/lib/api/account';

export default function Feedback() {
  const [rating, setRating] = useState<'up' | 'down' | null>(null);
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async () => {
    if (!rating) return;
    setSubmitting(true);
    try {
      await submitFeedback({ rating, message_preview: note.slice(0, 200) || undefined });
      setDone(true);
    } catch {
      // ignore — feedback is best-effort
      setDone(true);
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
        <Stack.Screen options={{ title: 'Thanks' }} />
        <View style={{ flex: 1, padding: 24, gap: 16, justifyContent: 'center' }}>
          <Text
            style={{
              fontFamily: Fonts.serifBold,
              fontSize: 22,
              color: Colors.textPrimary,
              textAlign: 'center',
            }}>
            Thanks for the feedback
          </Text>
          <Text
            style={{
              color: Colors.textSecondary,
              fontSize: 14,
              lineHeight: 21,
              textAlign: 'center',
            }}>
            It helps us tune WondrChat for people in your situation.
          </Text>
          <Button label="Back to Settings" fullWidth size="lg" onPress={() => router.back()} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Send feedback' }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            How has WondrChat been overall?
          </Text>

          <View style={{ flexDirection: 'row', gap: 10 }}>
            <RatingChip
              label="Helpful"
              Icon={ThumbsUp}
              selected={rating === 'up'}
              onPress={() => setRating('up')}
            />
            <RatingChip
              label="Could be better"
              Icon={ThumbsDown}
              selected={rating === 'down'}
              onPress={() => setRating('down')}
            />
          </View>

          <TextField
            label="Anything specific? (optional)"
            multiline
            placeholder="What worked, what didn't, what you wish it could do…"
            value={note}
            onChangeText={setNote}
            style={{ minHeight: 100, paddingTop: 12, textAlignVertical: 'top' }}
          />

          <Button
            label={submitting ? 'Sending…' : 'Send feedback'}
            fullWidth
            size="lg"
            loading={submitting}
            disabled={!rating}
            onPress={submit}
          />
          <Button label="Cancel" variant="ghost" fullWidth onPress={() => router.back()} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function RatingChip({
  label,
  Icon,
  selected,
  onPress,
}: {
  label: string;
  Icon: typeof ThumbsUp;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      style={({ pressed }) => ({
        flex: 1,
        flexDirection: 'row',
        gap: 8,
        alignItems: 'center',
        justifyContent: 'center',
        padding: 14,
        borderRadius: Radius.pill,
        borderWidth: selected ? 2 : 1,
        borderColor: selected ? Colors.primary : Colors.border,
        backgroundColor: selected
          ? Colors.primarySoft
          : pressed
            ? Colors.sidebarBg
            : Colors.surfaceMuted,
      })}>
      <Icon size={18} color={selected ? Colors.primary : Colors.textMuted} />
      <Text
        style={{
          color: selected ? Colors.primary : Colors.textPrimary,
          fontFamily: Fonts.sansSemiBold,
          fontSize: 13,
        }}>
        {label}
      </Text>
    </Pressable>
  );
}
