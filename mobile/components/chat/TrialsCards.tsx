import { Bookmark, BookmarkCheck, ExternalLink, Microscope } from 'lucide-react-native';
import { Linking, Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { useWatchlist } from '@/hooks/useWatchlist';
import type { ChatClinicalTrialsBlock } from '@shared/types';

interface Props {
  trials?: ChatClinicalTrialsBlock | null;
}

const BAND_LABELS: Record<string, { label: string; color: string }> = {
  strong: { label: 'Strong match', color: Colors.primary },
  moderate: { label: 'Moderate match', color: Colors.accent },
  general: { label: 'General match', color: Colors.textMuted },
};

/** Recruiting / enrolling = actionable (teal); everything else = muted. */
function StatusPill({ status }: { status: string }) {
  const recruiting = /^(recruiting|enrolling)/i.test(status);
  return (
    <View
      style={{
        flexShrink: 0,
        paddingHorizontal: 8,
        paddingVertical: 3,
        borderRadius: Radius.pill,
        backgroundColor: recruiting ? Colors.primarySoft : Colors.sidebarBg,
      }}>
      <Text
        numberOfLines={1}
        style={{
          color: recruiting ? Colors.primary : Colors.textMuted,
          fontSize: 11,
          fontFamily: Fonts.sansSemiBold,
        }}>
        {status}
      </Text>
    </View>
  );
}

export function TrialsCards({ trials }: Props) {
  const { isSaved, save, remove } = useWatchlist();
  if (!trials || !trials.trials || trials.trials.length === 0) return null;

  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Microscope size={14} color={Colors.textMuted} />
        <Text
          style={{
            color: Colors.textMuted,
            fontFamily: Fonts.sansMedium,
            fontSize: 11,
            letterSpacing: 0.5,
          }}>
          {trials.found} OF {trials.total} CLINICAL TRIALS
        </Text>
      </View>
      <View style={{ gap: 8 }}>
        {trials.trials.slice(0, 5).map((t) => {
          const band = t.relevance?.band ? BAND_LABELS[t.relevance.band] : null;
          const url = t.url || `https://clinicaltrials.gov/study/${t.nct_id}`;
          const saved = isSaved(t.nct_id);
          return (
            <View
              key={t.nct_id}
              style={{
                borderWidth: 1,
                borderColor: Colors.border,
                borderRadius: Radius.lg,
                padding: 14,
                backgroundColor: Colors.surface,
                gap: 8,
                shadowColor: Colors.textPrimary,
                shadowOpacity: 0.06,
                shadowRadius: 8,
                shadowOffset: { width: 0, height: 2 },
                elevation: 2,
              }}>
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                }}>
                <Text style={{ color: Colors.textMuted, fontFamily: Fonts.sansMedium, fontSize: 11 }}>
                  {t.nct_id}
                  {t.phase ? ` · ${t.phase}` : ''}
                </Text>
                {t.status ? <StatusPill status={t.status} /> : null}
              </View>
              <Text
                style={{
                  color: Colors.textPrimary,
                  fontFamily: Fonts.sansSemiBold,
                  fontSize: 14,
                  lineHeight: 19,
                }}
                numberOfLines={3}>
                {t.title}
              </Text>
              {band && (
                <Text
                  style={{ color: band.color, fontFamily: Fonts.sansSemiBold, fontSize: 11 }}>
                  {band.label}
                </Text>
              )}
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginTop: 2,
                }}>
                <Pressable
                  onPress={() => Linking.openURL(url).catch(() => {})}
                  accessibilityRole="link"
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  <ExternalLink size={13} color={Colors.primary} />
                  <Text
                    style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 12 }}>
                    View on ClinicalTrials.gov
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() =>
                    saved
                      ? remove(t.nct_id)
                      : save({ nct_id: t.nct_id, title: t.title, phase: t.phase, url })
                  }
                  accessibilityRole="button"
                  accessibilityLabel={saved ? 'Unsave trial' : 'Save trial to watchlist'}
                  hitSlop={8}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  {saved ? (
                    <BookmarkCheck size={14} color={Colors.primary} />
                  ) : (
                    <Bookmark size={14} color={Colors.textMuted} />
                  )}
                  <Text
                    style={{
                      color: saved ? Colors.primary : Colors.textMuted,
                      fontFamily: Fonts.sansMedium,
                      fontSize: 12,
                    }}>
                    {saved ? 'Saved' : 'Save'}
                  </Text>
                </Pressable>
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}
