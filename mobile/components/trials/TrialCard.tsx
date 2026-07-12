/**
 * TrialCard — Direction E. The single shared clinical-trial card used by the
 * Tools screen and the in-chat trial list.
 *
 * Layout: match band (tier + eligibility) → plain-language summary → optional
 * warning callout → facts panel (Treatment / Who can join / Study size /
 * Nearest site / Study ID) → actions (View button + Save).
 */

import { Linking, Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
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

/** Rewrite a scored warning into second-person patient copy, e.g.
 *  "May require MSS tumors; patient is MSI-H" -> "May require MSS tumors — your profile is MSI-H." */
function patientizeWarning(w: string): string {
  let out = w.replace(/;\s*patient is/i, ' — your profile is');
  if (!/[.!?]$/.test(out)) out += '.';
  return out;
}

function factsFor(t: ChatClinicalTrial): { key: string; value: string }[] {
  const drugs = (t.interventions ?? []).map((i) => i.name).filter(Boolean);
  const treatment =
    drugs.length === 0
      ? 'See study for details'
      : drugs.slice(0, 3).join(' + ') + (drugs.length > 3 ? ' + others' : '');

  const site = t.locations?.[0];
  let nearest = 'Location not listed';
  if (site && (site.facility || site.city)) {
    const facilityShort = (site.facility || '').split(' / ')[0];
    const cityState = [site.city, site.state].filter(Boolean).join(', ');
    const d = t.nearest_distance_miles;
    const dist = d == null ? '' : d === 0 ? ' (~0 mi)' : ` (${d} mi)`;
    nearest = [facilityShort, cityState].filter(Boolean).join(' · ') + dist;
  }

  return [
    { key: 'Treatment', value: treatment },
    { key: 'Who can join', value: whoCanJoin(t.eligibility) },
    {
      key: 'Study size',
      value: t.enrollment_count != null ? `${t.enrollment_count} participants` : 'Not specified',
    },
    { key: 'Nearest site', value: nearest },
    { key: 'Study ID', value: t.nct_id },
  ];
}

interface Props {
  trial: ChatClinicalTrial;
  saved?: boolean;
  onToggleSave?: () => void;
}

export function TrialCard({ trial: t, saved, onToggleSave }: Props) {
  const band: Tier = (t.relevance?.band as Tier) || 'general';
  const tier = TIER[band];
  const eligibleLabel = t.likely_eligible === false ? 'Check criteria first' : 'Likely eligible';
  const url = t.url || `https://clinicaltrials.gov/study/${t.nct_id}`;
  const warning = t.relevance?.warnings?.[0];
  const summary = t.plain_summary || t.brief_summary || '';
  const facts = factsFor(t);

  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        backgroundColor: Colors.surface,
        overflow: 'hidden',
      }}>
      {/* Match band */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          paddingVertical: 9,
          paddingHorizontal: 14,
          backgroundColor: tier.bg,
        }}>
        <Text
          style={{
            color: tier.fg,
            fontFamily: Fonts.sansBold,
            fontSize: 11,
            letterSpacing: 0.5,
            textTransform: 'uppercase',
          }}>
          {tier.label}
        </Text>
        <Text style={{ color: tier.fg, fontFamily: Fonts.sansSemiBold, fontSize: 12 }}>
          {eligibleLabel}
        </Text>
      </View>

      {/* Body */}
      <View style={{ paddingTop: 12, paddingHorizontal: 14, paddingBottom: 14, gap: 12 }}>
        {summary ? (
          <Text
            style={{
              color: Colors.textPrimary,
              fontFamily: Fonts.sansSemiBold,
              fontSize: 15,
              lineHeight: 21,
            }}>
            {summary}
          </Text>
        ) : null}

        {/* Warning callout */}
        {warning ? (
          <View
            style={{
              flexDirection: 'row',
              gap: 9,
              alignItems: 'flex-start',
              backgroundColor: Colors.warningBg,
              borderRadius: Radius.sm,
              paddingVertical: 9,
              paddingHorizontal: 10,
            }}>
            <View
              style={{
                width: 18,
                height: 18,
                borderRadius: 9,
                backgroundColor: Colors.warning,
                alignItems: 'center',
                justifyContent: 'center',
              }}>
              <Text style={{ color: Colors.warningBg, fontFamily: Fonts.sansBold, fontSize: 11 }}>
                !
              </Text>
            </View>
            <Text style={{ flex: 1, color: Colors.warning, fontSize: 13, lineHeight: 18 }}>
              {patientizeWarning(warning)}
            </Text>
          </View>
        ) : null}

        {/* Facts panel */}
        <View
          style={{
            backgroundColor: Colors.surfaceMuted,
            borderRadius: Radius.md,
            paddingVertical: 12,
            paddingHorizontal: 14,
            gap: 8,
          }}>
          {facts.map((f) => (
            <View key={f.key} style={{ flexDirection: 'row', gap: 10 }}>
              <Text
                style={{
                  width: 92,
                  fontFamily: Fonts.sansSemiBold,
                  fontSize: 11,
                  color: Colors.textMuted,
                }}>
                {f.key}
              </Text>
              <Text style={{ flex: 1, color: Colors.textPrimary, fontSize: 12, lineHeight: 17 }}>
                {f.value}
              </Text>
            </View>
          ))}
        </View>

        {/* Actions */}
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Pressable
            onPress={() => Linking.openURL(url).catch(() => {})}
            accessibilityRole="button"
            accessibilityLabel="View on ClinicalTrials.gov"
            style={({ pressed }) => ({
              flex: 1,
              minHeight: 48,
              alignItems: 'center',
              justifyContent: 'center',
              paddingHorizontal: 10,
              borderRadius: Radius.md,
              backgroundColor: pressed ? Colors.primaryPressed : Colors.primary,
            })}>
            <Text style={{ color: Colors.surface, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
              View on ClinicalTrials.gov
            </Text>
          </Pressable>
          {onToggleSave && (
            <Pressable
              onPress={onToggleSave}
              accessibilityRole="button"
              accessibilityState={{ selected: !!saved }}
              accessibilityLabel={saved ? 'Saved' : 'Save trial'}
              style={({ pressed }) => ({
                minWidth: 86,
                minHeight: 48,
                alignItems: 'center',
                justifyContent: 'center',
                paddingHorizontal: 12,
                borderRadius: Radius.md,
                borderWidth: 1.5,
                borderColor: saved ? Colors.primarySoft : Colors.primary,
                backgroundColor: pressed
                  ? Colors.sidebarBg
                  : saved
                    ? Colors.primarySoft
                    : Colors.surface,
              })}>
              <Text style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
                {saved ? 'Saved ✓' : 'Save'}
              </Text>
            </Pressable>
          )}
        </View>
      </View>
    </View>
  );
}
