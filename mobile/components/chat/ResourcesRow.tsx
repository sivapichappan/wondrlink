import { ExternalLink } from 'lucide-react-native';
import { Linking, Pressable, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';
import type { ChatResource } from '@shared/types';

interface Props {
  resources?: ChatResource[];
}

export function ResourcesRow({ resources }: Props) {
  if (!resources || resources.length === 0) return null;

  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
      {resources.map((r, i) => {
        const label = r.title || r.name || r.url;
        return (
          <Pressable
            key={`${r.url}-${i}`}
            onPress={() => r.url && Linking.openURL(r.url).catch(() => {})}
            accessibilityRole="link"
            accessibilityLabel={`Open ${label}`}
            style={({ pressed }) => ({
              flexDirection: 'row',
              alignItems: 'center',
              gap: 4,
              paddingHorizontal: 10,
              paddingVertical: 6,
              borderRadius: 999,
              backgroundColor: pressed ? Colors.sidebarBg : Colors.surfaceMuted,
              borderWidth: 1,
              borderColor: Colors.border,
            })}>
            <ExternalLink size={12} color={Colors.primary} />
            <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 12 }}>
              {label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
