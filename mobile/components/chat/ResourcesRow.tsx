import { ExternalLink } from 'lucide-react-native';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';
import type { ChatResource } from '@shared/types';

interface Props {
  resources?: ChatResource[];
}

export function ResourcesRow({ resources }: Props) {
  if (!resources || resources.length === 0) return null;

  return (
    <View style={{ gap: 4 }}>
      <Text style={styles.label}>SOURCES</Text>
      <View style={styles.row}>
        {resources.map((r, i) => {
          const label = r.title || r.name || r.url;
          return (
            <Pressable
              key={`${r.url}-${i}`}
              onPress={() => r.url && Linking.openURL(r.url).catch(() => {})}
              accessibilityRole="link"
              accessibilityLabel={`Open ${label}`}
              style={styles.chip}>
              <View style={styles.chipInner}>
                <ExternalLink size={11} color={Colors.primary} style={{ marginRight: 4 }} />
                <Text numberOfLines={1} ellipsizeMode="tail" style={styles.chipText}>
                  {label}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    color: Colors.textMuted,
    fontSize: 10,
    fontFamily: Fonts.sansMedium,
    letterSpacing: 0.5,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
  },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surfaceMuted,
    maxWidth: '100%',
  },
  chipInner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  chipText: {
    color: Colors.primary,
    fontFamily: Fonts.sansMedium,
    fontSize: 11,
    flexShrink: 1,
  },
});
