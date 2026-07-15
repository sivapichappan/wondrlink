/**
 * TrialCard, the single shared clinical-trial card (Tools screen + in-chat).
 *
 * Layout: match band (tier + eligibility) → plain-language summary → optional
 * warning callout → facts (Treatment / Who can join / Nearest site inline;
 * Study size + Study ID behind a "More details" tap) → actions (View + Save).
 */

import { ChevronDown, ChevronUp } from 'lucide-react-native';
import { useState } from 'react';
import { Linking, Pressable, Text, View } from 'react-native';

import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import type { ChatClinicalTrial } from '@shared/types';

type Tier = 'strong' | 'moderate' | 'general';

const TIER: Record<Tier, { bg: string; fg: string; label: string }> = {
  strong: { bg: Colors.primarySoft, fg: Colors.primary, label: 'Strong match' },
  moderate: { bg: Colors.warningBg, fg: Colors.warning, label: 'Moderate match' },
  general: { bg: Colors.sidebarBg, fg: Colors.textSecondary, label: 'General match' },
};

function titleCase(s?: string): string {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

/** "Ages 18+ · All sexes" from the eligibility object. */
function whoCanJoin(e?: ChatClinicalTrial['eligibility']): string {
  if (!e) return 'See study for details';
  const min = (e.min_age || '').replace(/\s*Years?/i, '').trim();
  const max = (e.max_age || '').replace(/\s*Years?/i, '').trim();
  let ages = '';
  if (min && max) ages = `Ages ${min}–${max}`;
  else if (min) ages = `Ages ${min}+`;
  else if (max) ages = `Up to ${max}`;
  const sex = (e.sex || '').toUpperCase();
  const sexLabel = sex === 'ALL' ? 'All sexes' : sex ? `${titleCase(sex)} only` : '';
  return [ages, sexLabel].filter(Boolean).join(' · ') || 'See study for details';
}

/** "May require MSS tumors; patient is MSI-H" -> "…— your profile is MSI-H." */
function patientizeWarning(w: string): string {
  let out = w.replace(/;\s*patient is/i, ', your profile is');
  if (!/[.!?]$/.test(out)) out += '.';
  return out;
}

function treatmentOf(t: ChatClinicalTrial): string {
  const drugs = (t.interventions ?? []).map((i) => i.name).filter(Boolean);
  if (drugs.length === 0) return 'See study for details';
  return drugs.slice(0, 3).join(' + ') + (drugs.length > 3 ? ' + others' : '');
}

function nearestOf(t: ChatClinicalTrial): string {
  const site = t.locations?.[0];
  if (!site || !(site.facility || site.city)) return 'Location not listed';
  const facilityShort = (site.facility || '').split(' / ')[0];
  const cityState = [site.city, site.state].filter(Boolean).join(', ');
  const d = t.nearest_distance_miles;
  const dist = d == null ? '' : d === 0 ? ' (~0 mi)' : ` (${d} mi)`;
  return [facilityShort, cityState].filter(Boolean).join(' · ') + dist;
}

interface Props {
  trial: ChatClinicalTrial;
  saved?: boolean;
  onToggleSave?: () => void;
}

export function TrialCard({ trial: t, saved, onToggleSave }: Props) {
  const [showMore, setShowMore] = useState(false);
  const band: Tier = (t.relevance?.band as Tier) || 'general';
  const tier = TIER[band];
  const eligibleLabel = t.likely_eligible === false ? 'Check criteria first' : 'Likely eligible';
  const url = t.url || `https://clinicaltrials.gov/study/${t.nct_id}`;
  const warning = t.relevance?.warnings?.[0];
  const reasons = (t.relevance?.reasons ?? []).slice(0, 2).join(' · ');
  const summary = t.plain_summary || t.brief_summary || '';

  const primaryFacts = [
    { key: 'Treatment', value: treatmentOf(t) },
    { key: 'Who can join', value: whoCanJoin(t.eligibility) },
    { key: 'Nearest site', value: nearestOf(t) },
  ];
  const moreFacts = [
    { key: 'Study size', value: t.enrollment_count != null ? `${t.enrollment_count} participants` : 'Not specified' },
    { key: 'Study ID', value: t.nct_id },
  ];

  return (
    <View style={{ borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.lg, backgroundColor: Colors.surface, overflow: 'hidden' }}>
      {/* Match band */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: Spacing.sm,
          paddingVertical: 9,
          paddingHorizontal: Spacing.lg,
          backgroundColor: tier.bg,
        }}>
        <Text style={{ color: tier.fg, fontFamily: Fonts.sansBold, fontSize: FontSize.xs, letterSpacing: 0.5, textTransform: 'uppercase' }}>
          {tier.label}
        </Text>
        <Text style={{ color: tier.fg, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.sm }}>{eligibleLabel}</Text>
      </View>

      {/* Body */}
      <View style={{ padding: Spacing.lg, gap: Spacing.md }}>
        {summary ? (
          <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.lg, lineHeight: 21 }}>{summary}</Text>
        ) : null}

        {/* Why this matches (top-2 reasons — web parity) */}
        {reasons ? (
          <Text style={{ color: Colors.textSecondary, fontSize: FontSize.sm, lineHeight: 18 }}>{reasons}</Text>
        ) : null}

        {/* Warning callout */}
        {warning ? (
          <View style={{ flexDirection: 'row', gap: Spacing.sm, alignItems: 'flex-start', backgroundColor: Colors.warningBg, borderRadius: Radius.sm, padding: Spacing.sm }}>
            <View style={{ width: 18, height: 18, borderRadius: Radius.pill, backgroundColor: Colors.warning, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ color: Colors.warningBg, fontFamily: Fonts.sansBold, fontSize: FontSize.xs }}>!</Text>
            </View>
            <Text style={{ flex: 1, color: Colors.warning, fontSize: FontSize.base, lineHeight: 18 }}>{patientizeWarning(warning)}</Text>
          </View>
        ) : null}

        {/* Facts panel */}
        <View style={{ backgroundColor: Colors.surfaceMuted, borderRadius: Radius.md, padding: Spacing.md, gap: Spacing.sm }}>
          {primaryFacts.map((f) => (
            <Fact key={f.key} k={f.key} v={f.value} />
          ))}
          {showMore && moreFacts.map((f) => <Fact key={f.key} k={f.key} v={f.value} />)}
          <Pressable onPress={() => setShowMore((s) => !s)} accessibilityRole="button" accessibilityLabel={showMore ? 'Fewer details' : 'More details'} hitSlop={6}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingTop: 2 }}>
              <Text style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.sm }}>{showMore ? 'Fewer details' : 'More details'}</Text>
              {showMore ? <ChevronUp size={14} color={Colors.primary} /> : <ChevronDown size={14} color={Colors.primary} />}
            </View>
          </Pressable>
        </View>

        {/* Actions, visuals on static inner Views (NativeWind rule). */}
        <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
          <Pressable
            onPress={() => Linking.openURL(url).catch(() => {})}
            accessibilityRole="button"
            accessibilityLabel="View on ClinicalTrials.gov"
            android_ripple={{ color: 'rgba(255,255,255,0.18)' }}
            style={{ flex: 1 }}>
            <View style={{ minHeight: 48, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Spacing.sm, borderRadius: Radius.md, backgroundColor: Colors.primary }}>
              <Text style={{ color: Colors.surface, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.md }}>View on ClinicalTrials.gov</Text>
            </View>
          </Pressable>
          {onToggleSave && (
            <Pressable
              onPress={onToggleSave}
              accessibilityRole="button"
              accessibilityState={{ selected: !!saved }}
              accessibilityLabel={saved ? 'Saved' : 'Save trial'}
              hitSlop={8}
              android_ripple={{ color: Colors.sidebarBg }}>
              <View
                style={{
                  minWidth: 86,
                  minHeight: 48,
                  alignItems: 'center',
                  justifyContent: 'center',
                  paddingHorizontal: Spacing.md,
                  borderRadius: Radius.md,
                  borderWidth: 1.5,
                  borderColor: saved ? Colors.primarySoft : Colors.primary,
                  backgroundColor: saved ? Colors.primarySoft : Colors.surface,
                }}>
                <Text style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.md }}>{saved ? 'Saved ✓' : 'Save'}</Text>
              </View>
            </Pressable>
          )}
        </View>
      </View>
    </View>
  );
}

function Fact({ k, v }: { k: string; v: string }) {
  return (
    <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
      <Text style={{ width: 92, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.xs, color: Colors.textMuted }}>{k}</Text>
      <Text style={{ flex: 1, color: Colors.textPrimary, fontSize: FontSize.sm, lineHeight: 17 }}>{v}</Text>
    </View>
  );
}
