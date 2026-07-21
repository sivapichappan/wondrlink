/**
 * EscalationCard — the in-thread safety card for T1/T2/MH classifier tiers
 * (supervisor safety layer). Renders ABOVE the crisis response text.
 *
 *   T1: emergency styling, "Call 911" first, care team second.
 *   T2: urgent styling, "Call my care team" first, 911 second, plus the
 *       "Log this symptom" action (timestamped patient_events row).
 *   MH: warm styling (no siren), 988 + Crisis Text Line from
 *       crisis_resources; never the medical card.
 *
 * T3 does NOT use this card — it rides the existing UrgencyBanner.
 * NativeWind rule: Pressable visuals live on static inner Views.
 */

import { AlertCircle, Check, ClipboardList, Heart, LifeBuoy, Phone } from 'lucide-react-native';
import { useState } from 'react';
import { Linking, Pressable, Text, View } from 'react-native';

import { useNavOverlay } from '@/components/common/NavOverlay';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { logSymptom } from '@/lib/api/chat';
import type { ChatSafety, CrisisResources } from '@shared/types';

interface Props {
  safety?: ChatSafety | null;
  crisisResources?: CrisisResources | null;
}

function CallButton({
  label,
  primary,
  tel,
  onPress,
  icon,
}: {
  label: string;
  primary: boolean;
  tel?: string;
  onPress?: () => void;
  icon?: 'phone' | 'help';
}) {
  const handle = onPress ?? (() => Linking.openURL(tel ?? '').catch(() => {}));
  const Icon = icon === 'help' ? LifeBuoy : Phone;
  return (
    <Pressable onPress={handle} accessibilityRole="button" accessibilityLabel={label}>
      <View
        style={{
          flexDirection: 'row',
          gap: 6,
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: Spacing.md,
          paddingVertical: Spacing.sm,
          borderRadius: 999,
          backgroundColor: primary ? Colors.danger : Colors.surface,
          borderWidth: 1,
          borderColor: Colors.danger,
        }}>
        <Icon size={14} color={primary ? Colors.surface : Colors.danger} />
        <Text
          style={{
            color: primary ? Colors.surface : Colors.danger,
            fontFamily: Fonts.sansSemiBold,
            fontSize: FontSize.sm,
          }}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

function LogSymptomChip({ safety }: { safety: ChatSafety }) {
  const [state, setState] = useState<'idle' | 'busy' | 'done' | 'error'>('idle');

  if (state === 'done') {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Check size={14} color={Colors.primary} />
        <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted }}>
          Logged with today&apos;s date. You can show this to your care team.
        </Text>
      </View>
    );
  }

  const send = async () => {
    setState('busy');
    try {
      await logSymptom({ tier: safety.tier, category: safety.category });
      setState('done');
    } catch {
      setState('error');
    }
  };

  return (
    <Pressable onPress={send} disabled={state === 'busy'} accessibilityRole="button">
      <View
        style={{
          flexDirection: 'row',
          gap: 6,
          alignItems: 'center',
          alignSelf: 'flex-start',
          paddingHorizontal: Spacing.md,
          paddingVertical: Spacing.sm,
          borderRadius: 999,
          borderWidth: 1,
          borderColor: Colors.border,
          backgroundColor: Colors.surface,
          opacity: state === 'busy' ? 0.6 : 1,
        }}>
        <ClipboardList size={14} color={Colors.textPrimary} />
        <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.sm }}>
          {state === 'error' ? 'Try logging again' : 'Log this symptom'}
        </Text>
      </View>
    </Pressable>
  );
}

export function EscalationCard({ safety, crisisResources }: Props) {
  // Hooks must run unconditionally; the null-return happens after.
  const { openHelp } = useNavOverlay();
  if (!safety || safety.tier === 'T3') return null;

  const en = safety.emergency_number || '911';
  const isMH = safety.tier === 'MH';
  const bg = isMH ? Colors.primarySoft : Colors.emergencyBg;
  const accent = isMH ? Colors.primary : Colors.danger;

  return (
    <View
      style={{
        gap: Spacing.sm,
        padding: Spacing.md,
        borderRadius: Radius.md,
        backgroundColor: bg,
        borderWidth: 1,
        borderColor: accent,
      }}>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        {isMH ? <Heart size={18} color={accent} /> : <AlertCircle size={18} color={accent} />}
        <Text
          style={{
            flex: 1,
            color: accent,
            fontFamily: Fonts.sansSemiBold,
            fontSize: FontSize.md,
            lineHeight: 20,
          }}>
          {safety.patient_line}
        </Text>
      </View>

      {isMH ? (
        <View style={{ gap: Spacing.xs }}>
          {(crisisResources?.resources ?? []).map((r) => (
            <Text key={r.name} style={{ fontSize: FontSize.sm, color: Colors.textPrimary, lineHeight: 19 }}>
              {r.name}: {r.contact}
            </Text>
          ))}
          <View style={{ flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.xs }}>
            <Pressable
              onPress={() => Linking.openURL('tel:988').catch(() => {})}
              accessibilityRole="button"
              accessibilityLabel="Call or text 988">
              <View
                style={{
                  flexDirection: 'row',
                  gap: 6,
                  alignItems: 'center',
                  paddingHorizontal: Spacing.md,
                  paddingVertical: Spacing.sm,
                  borderRadius: 999,
                  backgroundColor: Colors.primary,
                }}>
                <Phone size={14} color={Colors.surface} />
                <Text style={{ color: Colors.surface, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.sm }}>
                  Call 988
                </Text>
              </View>
            </Pressable>
          </View>
        </View>
      ) : (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm }}>
          {/* No stored care-team number yet (arrives with the visit-recorder
              workstream), so the care-team action opens the SOS Help sheet
              with all helplines rather than a dead dialer. */}
          {safety.tier === 'T1' ? (
            <>
              <CallButton label={`Call ${en}`} tel={`tel:${en}`} primary />
              <CallButton label="My care team" onPress={openHelp} icon="help" primary={false} />
            </>
          ) : (
            <>
              <CallButton label="Reach my care team" onPress={openHelp} icon="help" primary />
              <CallButton label={`Call ${en}`} tel={`tel:${en}`} primary={false} />
            </>
          )}
        </View>
      )}

      {safety.offer_symptom_log ? <LogSymptomChip safety={safety} /> : null}
    </View>
  );
}
