import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { AlertCircle, Check } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useProfile } from '@/hooks/useCare';
import { fetchCancerOptions, updateCancerSlug } from '@/lib/api/care';
import { ApiError, extractErrorMessage } from '@/lib/api/client';
import type { CancerOption, PatientRole } from '@shared/types';

const ROLES: { value: PatientRole; label: string; desc: string }[] = [
  { value: 'patient', label: 'Patient', desc: "I'm the one diagnosed" },
  { value: 'caregiver', label: 'Caregiver', desc: 'I’m supporting someone else' },
];

export default function CancerSwitcherScreen() {
  const qc = useQueryClient();
  const ack = useAcknowledgement();
  const profile = useProfile();

  const options = useQuery({
    queryKey: ['cancer_options'],
    queryFn: () => fetchCancerOptions(false),
    staleTime: 5 * 60_000,
  });

  const initialSlug = (ack.data?.cancer_slug ?? null) as string | null;
  const initialRole = (profile.data?.profile as { patient?: { role?: PatientRole } } | undefined)
    ?.patient?.role;

  const [pickedSlug, setPickedSlug] = useState<string | null>(initialSlug);
  const [pickedRole, setPickedRole] = useState<PatientRole>(initialRole ?? 'patient');
  const [error, setError] = useState<string | null>(null);

  // Keep state in sync if data loads after first render.
  useEffect(() => {
    if (initialSlug && !pickedSlug) setPickedSlug(initialSlug);
  }, [initialSlug, pickedSlug]);

  const save = useMutation({
    mutationFn: () => {
      if (!pickedSlug) throw new Error('Pick a cancer first.');
      return updateCancerSlug(pickedSlug, pickedRole);
    },
    onSuccess: async () => {
      // Refresh anything that depends on cancer focus.
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['acknowledgement'] }),
        qc.invalidateQueries({ queryKey: ['profile'] }),
        qc.invalidateQueries({ queryKey: ['hero'] }),
        qc.invalidateQueries({ queryKey: ['care_snapshot'] }),
      ]);
      router.back();
    },
    onError: (e) => {
      const fallback =
        e instanceof ApiError ? `Could not update (${e.status})` : 'Could not update cancer focus.';
      setError(
        e instanceof ApiError
          ? extractErrorMessage(e.body, fallback)
          : extractErrorMessage(e, fallback),
      );
    },
  });

  const onSave = () => {
    if (!pickedSlug) {
      setError('Pick a cancer first.');
      return;
    }
    // Confirm when switching away from the existing cancer — chat history
    // stays, but personalised retrievals will pivot to the new corpus.
    if (initialSlug && initialSlug !== pickedSlug) {
      Alert.alert(
        'Switch cancer focus?',
        'Your chat history stays, but new answers will be tailored to your new selection. You can switch back any time.',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Switch', onPress: () => save.mutate() },
        ],
      );
    } else {
      save.mutate();
    }
  };

  if (options.isLoading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={Colors.primary} />
      </View>
    );
  }

  if (options.isError || !options.data) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
        <View style={{ padding: 20, gap: 12 }}>
          <View
            style={{
              flexDirection: 'row',
              gap: 10,
              padding: 14,
              borderRadius: Radius.md,
              backgroundColor: Colors.warningBg,
              borderWidth: 1,
              borderColor: Colors.warning,
            }}>
            <AlertCircle size={18} color={Colors.warning} />
            <Text style={{ flex: 1, color: Colors.textPrimary, fontSize: 13, lineHeight: 19 }}>
              Could not load the cancer list. Check your connection and try again.
            </Text>
          </View>
          <Button label="Retry" variant="secondary" onPress={() => options.refetch()} />
        </View>
      </SafeAreaView>
    );
  }

  const cancers = options.data.options;
  const dirty = pickedSlug !== null && (pickedSlug !== initialSlug || pickedRole !== initialRole);
  const canSave = !!pickedSlug && (dirty || !initialSlug);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={{ padding: 20, gap: 16, paddingBottom: 24 }}
          keyboardShouldPersistTaps="handled">
          <View style={{ gap: 4 }}>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
              Cancer focus
            </Text>
            <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>
              WondrChat tailors retrievals, treatment context, and trial matches to whichever
              cancer you select here. You can change this any time.
            </Text>
          </View>

          <FieldLabel>Which cancer should WondrChat focus on?</FieldLabel>
          <View style={{ gap: 8 }}>
            {cancers.map((c) => (
              <CancerCard
                key={c.slug}
                option={c}
                selected={pickedSlug === c.slug}
                onPress={() => {
                  setPickedSlug(c.slug);
                  setError(null);
                }}
              />
            ))}
          </View>

          <FieldLabel>Are you the patient or supporting someone else?</FieldLabel>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {ROLES.map((r) => {
              const selected = pickedRole === r.value;
              return (
                <Pressable
                  key={r.value}
                  onPress={() => setPickedRole(r.value)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  style={({ pressed }) => ({
                    flex: 1,
                    borderRadius: Radius.md,
                    borderWidth: selected ? 2 : 1,
                    borderColor: selected ? Colors.primary : Colors.border,
                    backgroundColor: selected
                      ? Colors.sidebarBg
                      : pressed
                        ? Colors.surfaceMuted
                        : Colors.surface,
                  })}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', padding: 12 }}>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text
                        style={{
                          color: selected ? Colors.primary : Colors.textPrimary,
                          fontFamily: Fonts.sansSemiBold,
                          fontSize: 14,
                        }}>
                        {r.label}
                      </Text>
                      <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
                        {r.desc}
                      </Text>
                    </View>
                    {selected && (
                      <Check size={18} color={Colors.primary} style={{ marginLeft: 8 }} />
                    )}
                  </View>
                </Pressable>
              );
            })}
          </View>

          {error && (
            <Text style={{ color: Colors.danger, fontSize: 13, lineHeight: 18 }}>{error}</Text>
          )}
        </ScrollView>

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
            label={save.isPending ? 'Saving…' : 'Save focus'}
            size="lg"
            fullWidth
            loading={save.isPending}
            disabled={!canSave}
            leadingIcon={!save.isPending ? <Check size={18} color={Colors.surface} /> : undefined}
            onPress={onSave}
          />
          <Button
            label="Cancel"
            variant="ghost"
            fullWidth
            onPress={() => router.back()}
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
      {children}
    </Text>
  );
}

function CancerCard({
  option,
  selected,
  onPress,
}: {
  option: CancerOption;
  selected: boolean;
  onPress: () => void;
}) {
  const accent = option.accent_color || Colors.primary;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      style={({ pressed }) => ({
        borderRadius: Radius.lg,
        borderWidth: selected ? 2 : 1,
        borderColor: selected ? accent : Colors.border,
        backgroundColor: selected
          ? Colors.sidebarBg
          : pressed
            ? Colors.surfaceMuted
            : Colors.surface,
      })}>
      <View style={{ flexDirection: 'row', alignItems: 'center', padding: 14 }}>
        <View
          style={{
            width: 38,
            height: 38,
            borderRadius: 19,
            backgroundColor: accent,
            alignItems: 'center',
            justifyContent: 'center',
            marginRight: 12,
          }}>
          <Text style={{ color: Colors.surface, fontFamily: Fonts.sansBold, fontSize: 13 }}>
            {option.short_name.slice(0, 3).toUpperCase()}
          </Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text
            numberOfLines={1}
            ellipsizeMode="tail"
            style={{
              color: selected ? accent : Colors.textPrimary,
              fontFamily: Fonts.sansSemiBold,
              fontSize: 15,
            }}>
            {option.display_name}
          </Text>
          <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
            {option.doc_count > 0
              ? `Tailored from ${option.doc_count} guideline document${option.doc_count === 1 ? '' : 's'}`
              : option.ready
                ? 'Ready'
                : 'Preview — limited corpus'}
          </Text>
        </View>
        {selected && (
          <Check size={18} color={accent} style={{ marginLeft: 8 }} />
        )}
      </View>
    </Pressable>
  );
}
