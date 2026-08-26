import { Activity, TrendingDown, TrendingUp, Minus } from 'lucide-react-native';
import { Text, View } from 'react-native';

import { APP_NAME } from '@shared/branding';
import { Colors, Fonts, Radius } from '@/constants/theme';
import type { CareSnapshotResponse, Phq9Trend } from '@shared/types';

import { Sparkline } from './Sparkline';

interface Props {
  snapshot?: CareSnapshotResponse;
}

const TREND_META: Record<Phq9Trend, { label: string; color: string; Icon: typeof TrendingDown }> = {
  improving: { label: 'Improving', color: Colors.primary, Icon: TrendingDown },
  stable: { label: 'Stable', color: Colors.textMuted, Icon: Minus },
  worsening: { label: 'Worsening', color: Colors.danger, Icon: TrendingUp },
  none: { label: 'Not enough data', color: Colors.textMuted, Icon: Activity },
};

export function CareSnapshot({ snapshot }: Props) {
  if (!snapshot) return null;
  const trend = TREND_META[snapshot.phq9_trend];
  const Icon = trend.Icon;
  const scores = (snapshot.phq9_points ?? []).map((p) => p.score);
  const latest = scores.length > 0 ? scores[scores.length - 1] : null;

  return (
    <View
      style={{
        backgroundColor: Colors.surface,
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        padding: 16,
        gap: 12,
      }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
          Care snapshot
        </Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          <Icon size={14} color={trend.color} />
          <Text
            style={{ color: trend.color, fontSize: 12, fontFamily: Fonts.sansMedium }}>
            {trend.label}
          </Text>
        </View>
      </View>

      {scores.length > 0 ? (
        <View style={{ alignItems: 'center', gap: 6 }}>
          <Sparkline values={scores} width={260} height={68} />
          <Text style={{ color: Colors.textMuted, fontSize: 11 }}>
            How you've been feeling · {snapshot.phq9_count} check-in{snapshot.phq9_count === 1 ? '' : 's'}
          </Text>
        </View>
      ) : (
        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 18 }}>
          No check-ins yet. {APP_NAME} asks a couple of plain questions in the conversation, and what you say builds up here.
        </Text>
      )}

      <View style={{ flexDirection: 'row', gap: 12 }}>
        <Stat
          label="Latest PHQ-9"
          value={latest === null ? '—' : String(latest)}
        />
        <Stat
          label="Symptom check-in"
          value={
            snapshot.days_since_symptom === null
              ? '—'
              : `${snapshot.days_since_symptom}d ago`
          }
        />
      </View>
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View
      style={{
        flex: 1,
        padding: 10,
        borderRadius: Radius.sm,
        backgroundColor: Colors.sidebarBg,
      }}>
      <Text
        style={{
          color: Colors.textMuted,
          fontSize: 11,
          fontFamily: Fonts.sansMedium,
          letterSpacing: 0.5,
        }}>
        {label.toUpperCase()}
      </Text>
      <Text
        style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 18, marginTop: 4 }}>
        {value}
      </Text>
    </View>
  );
}
