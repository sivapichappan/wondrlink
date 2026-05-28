import { Stack, router } from 'expo-router';
import { Bookmark, ExternalLink, Trash2 } from 'lucide-react-native';
import { Alert, Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useWatchlist, type SavedTrial } from '@/hooks/useWatchlist';

export default function WatchlistScreen() {
  const { trials, loaded, remove, clear } = useWatchlist();

  const onClearAll = () => {
    Alert.alert('Clear watchlist?', 'This removes all saved trials from this device.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: clear },
    ]);
  };

  if (!loaded) return null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Saved trials' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 12, paddingBottom: 40 }}>
        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
          Trials you've bookmarked from chat. Saved locally on this device only.
        </Text>

        {trials.length === 0 ? (
          <EmptyState />
        ) : (
          trials.map((t) => <SavedTrialCard key={t.nct_id} trial={t} onRemove={() => remove(t.nct_id)} />)
        )}

        {trials.length > 0 && (
          <Button label="Clear all saved" variant="ghost" fullWidth onPress={onClearAll} />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function EmptyState() {
  return (
    <View
      style={{
        padding: 24,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.sidebarBg,
        alignItems: 'center',
        gap: 10,
      }}>
      <Bookmark size={28} color={Colors.primary} />
      <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 15, color: Colors.textPrimary }}>
        No trials saved yet
      </Text>
      <Text
        style={{
          color: Colors.textSecondary,
          fontSize: 13,
          lineHeight: 19,
          textAlign: 'center',
        }}>
        Bookmark any trial that appears in chat to track it here.
      </Text>
      <Button
        label="Browse clinical trials"
        variant="secondary"
        onPress={() => router.push('/tools/clinical-trials')}
      />
    </View>
  );
}

function SavedTrialCard({ trial, onRemove }: { trial: SavedTrial; onRemove: () => void }) {
  const url = trial.url || `https://clinicaltrials.gov/study/${trial.nct_id}`;
  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        padding: 14,
        gap: 8,
        backgroundColor: Colors.surface,
      }}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
        <View style={{ flex: 1 }}>
          <Text
            style={{ color: Colors.textMuted, fontFamily: Fonts.sansMedium, fontSize: 11 }}>
            {trial.nct_id}
            {trial.phase ? ` · ${trial.phase}` : ''}
          </Text>
          <Text
            style={{
              color: Colors.textPrimary,
              fontFamily: Fonts.sansSemiBold,
              fontSize: 14,
              lineHeight: 20,
              marginTop: 4,
            }}
            numberOfLines={3}>
            {trial.title}
          </Text>
        </View>
        <Pressable
          onPress={onRemove}
          accessibilityRole="button"
          accessibilityLabel="Remove trial"
          hitSlop={8}
          style={({ pressed }) => ({
            padding: 6,
            borderRadius: 8,
            backgroundColor: pressed ? Colors.surfaceMuted : 'transparent',
            marginLeft: 8,
          })}>
          <Trash2 size={16} color={Colors.textMuted} />
        </Pressable>
      </View>
      <Pressable
        onPress={() => Linking.openURL(url).catch(() => {})}
        accessibilityRole="link"
        style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <ExternalLink size={12} color={Colors.primary} />
        <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 12 }}>
          View on ClinicalTrials.gov
        </Text>
      </Pressable>
    </View>
  );
}
