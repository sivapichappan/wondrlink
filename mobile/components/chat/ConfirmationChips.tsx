/**
 * ConfirmationChips — the "is that right?" cards for facts WondrChat quietly
 * picked up in conversation (belief store, high-stakes pending queue).
 *
 * Yes -> POST /api/confirm_belief (fact becomes confirmed) -> quiet check state.
 * No  -> the fact is dropped and the card shows the gentle corrected question
 *        (the user answers it naturally in the composer).
 *
 * NativeWind rule: Pressable visuals live on static inner Views.
 */

import { Check, X } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { confirmBelief } from '@/lib/api/chat';
import type { PendingConfirmation } from '@shared/types';

type ChipState = 'idle' | 'busy' | 'confirmed' | 'rejected' | 'error';

export function ConfirmationChips({ confirmations }: { confirmations: PendingConfirmation[] }) {
  if (!confirmations?.length) return null;
  return (
    <View style={{ gap: Spacing.sm, marginTop: Spacing.xs }}>
      {confirmations.map((c) => (
        <ConfirmationChip key={c.id} confirmation={c} />
      ))}
    </View>
  );
}

function ConfirmationChip({ confirmation }: { confirmation: PendingConfirmation }) {
  const [state, setState] = useState<ChipState>('idle');
  const [followup, setFollowup] = useState<string | null>(null);

  const resolve = async (accept: boolean) => {
    setState('busy');
    try {
      const res = await confirmBelief(confirmation.id, accept);
      if (res.status === 'confirmed') {
        setState('confirmed');
      } else {
        setState('rejected');
        setFollowup(res.corrected_question ?? null);
      }
    } catch {
      // Expired/unknown chips (e.g. resolved on another device) fail closed.
      setState('error');
    }
  };

  if (state === 'confirmed') {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: Spacing.sm }}>
        <Check size={14} color={Colors.primary} />
        <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted }}>Noted, thanks for confirming.</Text>
      </View>
    );
  }
  if (state === 'rejected') {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: Spacing.sm }}>
        <X size={14} color={Colors.textMuted} />
        <Text style={{ flex: 1, fontSize: FontSize.sm, color: Colors.textMuted }}>
          {followup ?? 'Got it, disregarded.'}
        </Text>
      </View>
    );
  }
  if (state === 'error') {
    return (
      <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, paddingHorizontal: Spacing.sm }}>
        That confirmation expired.
      </Text>
    );
  }

  const busy = state === 'busy';
  return (
    <View
      style={{
        backgroundColor: Colors.sidebarBg,
        borderRadius: Radius.md,
        padding: Spacing.md,
        gap: Spacing.sm,
        opacity: busy ? 0.6 : 1,
      }}>
      <Text style={{ fontSize: FontSize.base, lineHeight: 19, color: Colors.textPrimary }}>
        {confirmation.prompt}
      </Text>
      <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
        <Pressable
          onPress={() => resolve(true)}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="Yes, that's right"
          style={{ flex: 1 }}>
          <View
            style={{
              minHeight: 40,
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: Radius.sm,
              backgroundColor: Colors.primary,
            }}>
            <Text style={{ color: Colors.surface, fontSize: FontSize.base, fontFamily: Fonts.sansSemiBold }}>
              Yes, that&apos;s right
            </Text>
          </View>
        </Pressable>
        <Pressable
          onPress={() => resolve(false)}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="No, that's not right"
          style={{ flex: 1 }}>
          <View
            style={{
              minHeight: 40,
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: Radius.sm,
              borderWidth: 1.5,
              borderColor: Colors.border,
              backgroundColor: Colors.surface,
            }}>
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.base, fontFamily: Fonts.sansSemiBold }}>
              Not quite
            </Text>
          </View>
        </Pressable>
      </View>
    </View>
  );
}
