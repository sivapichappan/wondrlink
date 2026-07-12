import { Microscope } from 'lucide-react-native';
import { Text, View } from 'react-native';

import { TrialCard } from '@/components/trials/TrialCard';
import { Colors, Fonts } from '@/constants/theme';
import { useWatchlist } from '@/hooks/useWatchlist';
import type { ChatClinicalTrialsBlock } from '@shared/types';

interface Props {
  trials?: ChatClinicalTrialsBlock | null;
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
          const url = t.url || `https://clinicaltrials.gov/study/${t.nct_id}`;
          const saved = isSaved(t.nct_id);
          return (
            <TrialCard
              key={t.nct_id}
              trial={t}
              saved={saved}
              onToggleSave={() =>
                saved ? remove(t.nct_id) : save({ nct_id: t.nct_id, title: t.title, phase: t.phase, url })
              }
            />
          );
        })}
      </View>
    </View>
  );
}
