/**
 * My Care (design screen 4) — the personal hub.
 *
 * Merges the old Care tab with a first-class profile entry: a profile card with
 * a client-DERIVED completeness bar, the cancer-focus switcher, the Care
 * snapshot, and the wellness check-ins list with Trends folded in as a footer
 * row (one home for both — deduped out of All tools).
 */

import { router } from 'expo-router';
import { Activity, ChevronRight, ChevronsUpDown, LineChart, Tag } from 'lucide-react-native';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { CareSnapshot } from '@/components/care/CareSnapshot';
import { TopBar } from '@/components/common/TopBar';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useCareSnapshot, useProfile } from '@/hooks/useCare';

const WELLNESS_CHECKS: { key: 'SYMPTOM' | 'PHQ9' | 'GAD7' | 'PSS10' | 'ISI'; label: string }[] = [
  { key: 'SYMPTOM', label: 'Symptom check-in' },
  { key: 'PHQ9', label: 'Depression (PHQ-9)' },
  { key: 'GAD7', label: 'Anxiety (GAD-7)' },
  { key: 'PSS10', label: 'Stress (PSS-10)' },
  { key: 'ISI', label: 'Sleep (ISI)' },
];

/** Fraction of the well-known profile sections that carry data (0–1). */
function completenessOf(profileData: unknown): number {
  const p = profileData as
    | {
        patient?: { age?: unknown; sex?: unknown; zipCode?: unknown };
        primaryDiagnosis?: { stage?: unknown; histology?: unknown; biomarkers?: Record<string, unknown> };
        treatments?: unknown[];
        symptoms?: unknown[];
      }
    | undefined;
  if (!p) return 0;
  const sections = [
    !!(p.patient?.age || p.patient?.sex || p.patient?.zipCode),
    !!(p.primaryDiagnosis?.stage || p.primaryDiagnosis?.histology),
    !!(p.primaryDiagnosis?.biomarkers && Object.keys(p.primaryDiagnosis.biomarkers).length > 0),
    !!(Array.isArray(p.treatments) && p.treatments.length > 0),
    !!(Array.isArray(p.symptoms) && p.symptoms.length > 0),
  ];
  return sections.filter(Boolean).length / sections.length;
}

export default function MyCareScreen() {
  const profile = useProfile();
  const snap = useCareSnapshot();
  const ack = useAcknowledgement();

  const p = profile.data?.profile as { patient?: { firstName?: string; name?: string }; primaryDiagnosis?: { stage?: string } } | undefined;
  const hasProfile = !!profile.data?.profile;
  const patient = p?.patient;
  const name = patient?.firstName || patient?.name || 'Your profile';
  const initials = (name || 'You').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
  const cancerDisplay = ack.data?.cancer_display ?? null;
  const stage = p?.primaryDiagnosis?.stage;
  const summary =
    profile.data?.patient_summary ||
    [stage ? `Stage ${stage}` : null, cancerDisplay].filter(Boolean).join(' · ') ||
    'Add your diagnosis and treatments';
  const pct = Math.round(completenessOf(profile.data?.profile) * 100);

  const days = snap.data?.days_since_symptom;
  const checkinDue = days == null || days >= 7;

  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <TopBar leading="back" backLabel="Home" onBack={() => router.replace('/')} title="My Care" />

      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
        {/* Profile card */}
        <Pressable onPress={() => router.push('/profile')} accessibilityRole="button" accessibilityLabel="View your profile">
          <View style={{ backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.lg, padding: 14, gap: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 11 }}>
              <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ color: Colors.primaryPressed, fontSize: 15, fontFamily: Fonts.sansBold }}>{initials}</Text>
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text numberOfLines={1} style={{ fontSize: 15, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>{name}</Text>
                <Text numberOfLines={1} style={{ fontSize: 12, color: Colors.textMuted, marginTop: 1 }}>{summary}</Text>
              </View>
              <ChevronRight size={18} color={Colors.primary} />
            </View>
            {hasProfile && (
              <>
                <View style={{ height: 4, borderRadius: 2, backgroundColor: Colors.border, overflow: 'hidden' }}>
                  <View style={{ width: `${pct}%`, height: '100%', backgroundColor: Colors.primary }} />
                </View>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={{ fontSize: 11, color: Colors.textMuted }}>Profile {pct}% complete</Text>
                  {pct < 100 && <Text style={{ fontSize: 11.5, fontFamily: Fonts.sansSemiBold, color: Colors.primary }}>Complete it →</Text>}
                </View>
              </>
            )}
          </View>
        </Pressable>

        {/* Cancer focus */}
        <Pressable onPress={() => router.push('/profile/cancer-switcher')} accessibilityRole="button" accessibilityLabel="Change cancer focus">
          <View style={{ backgroundColor: Colors.surfaceMuted, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.lg, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Tag size={18} color={Colors.primary} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>Cancer focus</Text>
              <Text style={{ fontSize: 12, color: Colors.textMuted, marginTop: 1 }}>{cancerDisplay ? `${cancerDisplay} · tailors answers & trials` : 'Pick your cancer type'}</Text>
            </View>
            <Text style={{ fontSize: 12, fontFamily: Fonts.sansSemiBold, color: Colors.primary }}>Switch</Text>
            <ChevronsUpDown size={14} color={Colors.primary} />
          </View>
        </Pressable>

        {/* Care snapshot */}
        <CareSnapshot snapshot={snap.data} />

        {/* Wellness check-ins + Trends footer */}
        <View style={{ backgroundColor: Colors.surfaceMuted, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.lg, padding: 14, gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Activity size={16} color={Colors.primary} />
            <Text style={{ flex: 1, fontSize: 14, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>Wellness check-ins</Text>
            {checkinDue && (
              <View style={{ backgroundColor: Colors.sosBg, borderRadius: Radius.pill, paddingHorizontal: 8, paddingVertical: 3 }}>
                <Text style={{ fontSize: 10, fontFamily: Fonts.sansBold, color: Colors.warning }}>DUE</Text>
              </View>
            )}
          </View>
          {WELLNESS_CHECKS.map((w) => (
            <Pressable key={w.key} onPress={() => router.push({ pathname: '/tools/screening', params: { instrument: w.key } })} accessibilityRole="button" accessibilityLabel={`Start ${w.label}`}>
              <View style={{ flexDirection: 'row', alignItems: 'center', height: 40, paddingHorizontal: 12, borderRadius: Radius.sm, backgroundColor: Colors.sidebarBg }}>
                <Text style={{ flex: 1, fontSize: 13.5, color: Colors.textPrimary }}>{w.label}</Text>
                <ChevronRight size={16} color={Colors.primary} />
              </View>
            </Pressable>
          ))}
          {/* Trends folded in */}
          <Pressable onPress={() => router.push('/tools/trends')} accessibilityRole="button" accessibilityLabel="View trends">
            <View style={{ flexDirection: 'row', alignItems: 'center', height: 42, paddingHorizontal: 12, borderRadius: Radius.sm, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border }}>
              <LineChart size={15} color={Colors.primary} />
              <Text style={{ flex: 1, fontSize: 13.5, fontFamily: Fonts.sansSemiBold, color: Colors.primary, marginLeft: 8 }}>Trends</Text>
              <ChevronRight size={16} color={Colors.primary} />
            </View>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}
