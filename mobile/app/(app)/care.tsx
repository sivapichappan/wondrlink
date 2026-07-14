/**
 * My Care (design screen 4) — the personal hub, calmer pass.
 *
 * First-class profile card with a client-DERIVED completeness bar, the cancer-
 * focus switcher, the Care snapshot, and a compact wellness card: one
 * "Start a check-in" entry + Trends (the 5 instrument rows collapse into the
 * picker rather than stacking on this screen).
 */

import { router } from 'expo-router';
import { Activity, ChevronRight, LineChart, Tag } from 'lucide-react-native';
import { Text, View } from 'react-native';

import { CareSnapshot } from '@/components/care/CareSnapshot';
import { LIFECYCLE_LABELS } from '@/components/common/LifecycleStageLine';
import { TopBar } from '@/components/common/TopBar';
import { Card } from '@/components/ui/Card';
import { IconCircle } from '@/components/ui/IconCircle';
import { ListRow } from '@/components/ui/ListRow';
import { Pill } from '@/components/ui/Pill';
import { Screen } from '@/components/ui/Screen';
import { Colors, FontSize, Fonts, Spacing } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useCareSnapshot, useProfile } from '@/hooks/useCare';

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
    'Chat with WondrChat and it learns as you go';
  // "What WondrChat knows": server coverage when available (lifecycle model),
  // client-derived completeness as a fallback against older servers.
  const coverage = profile.data?.coverage;
  const pct = Math.round((coverage?.score ?? completenessOf(profile.data?.profile)) * 100);
  const knowsLabel = coverage
    ? `WondrChat knows ${coverage.known_count} thing${coverage.known_count === 1 ? '' : 's'} about your care`
    : `Profile ${pct}% complete`;
  const stageLabel = LIFECYCLE_LABELS[profile.data?.lifecycle_stage ?? 'getting_to_know_you'];

  const days = snap.data?.days_since_symptom;
  const checkinDue = days == null || days >= 7;

  return (
    <Screen header={<TopBar leading="back" backLabel="Home" title="My Care" />}>
      {/* Profile card */}
      <Card onPress={() => router.push('/profile')} accessibilityLabel="View your profile" gap={Spacing.sm}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.md }}>
          <IconCircle size={44} bg={Colors.primarySoft}>
            <Text style={{ color: Colors.primaryPressed, fontSize: FontSize.lg, fontFamily: Fonts.sansBold }}>{initials}</Text>
          </IconCircle>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text numberOfLines={1} style={{ fontSize: FontSize.lg, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>{name}</Text>
            <Text numberOfLines={1} style={{ fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 1 }}>{summary}</Text>
          </View>
          <ChevronRight size={18} color={Colors.primary} />
        </View>
        {hasProfile && (
          <>
            <View style={{ height: 4, borderRadius: 2, backgroundColor: Colors.border, overflow: 'hidden' }}>
              <View style={{ width: `${pct}%`, height: '100%', backgroundColor: Colors.primary }} />
            </View>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text numberOfLines={1} style={{ flex: 1, fontSize: FontSize.xs, color: Colors.textMuted }}>
                {knowsLabel} · {stageLabel}
              </Text>
              {pct < 100 && <Text style={{ fontSize: FontSize.sm, fontFamily: Fonts.sansSemiBold, color: Colors.primary }}>Add details →</Text>}
            </View>
          </>
        )}
      </Card>

      {/* Cancer focus */}
      <Card variant="muted" onPress={() => router.push('/profile/cancer-switcher')} accessibilityLabel="Change cancer focus" padding={Spacing.md}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.md }}>
          <Tag size={18} color={Colors.primary} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: FontSize.md, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>Cancer focus</Text>
            <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 1 }}>{cancerDisplay ? `${cancerDisplay} · tailors answers & trials` : 'Pick your cancer type'}</Text>
          </View>
          <ChevronRight size={18} color={Colors.primary} />
        </View>
      </Card>

      {/* Care snapshot */}
      <CareSnapshot snapshot={snap.data} />

      {/* Wellness check-ins — collapsed to one entry + Trends */}
      <Card variant="muted" padding={Spacing.md} gap={Spacing.sm}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
          <Activity size={16} color={Colors.primary} />
          <Text style={{ flex: 1, fontSize: FontSize.md, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>Wellness check-ins</Text>
          {checkinDue && <Pill tone="accent">DUE</Pill>}
        </View>
        <ListRow
          fill="sidebar"
          icon={<IconCircle size={30} bg={Colors.surface}><Activity size={15} color={Colors.primary} /></IconCircle>}
          title="Start a check-in"
          subtitle="Symptom, mood, sleep & stress"
          onPress={() => router.push('/tools/screening')}
        />
        <ListRow
          fill="sidebar"
          icon={<IconCircle size={30} bg={Colors.surface}><LineChart size={15} color={Colors.primary} /></IconCircle>}
          title="Trends"
          subtitle="How your check-ins track over time"
          onPress={() => router.push('/tools/trends')}
        />
      </Card>
    </Screen>
  );
}
