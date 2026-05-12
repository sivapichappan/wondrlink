import { SafeAreaView } from 'react-native-safe-area-context';
import { Text, View } from 'react-native';

import { AI_DISCLOSURE_BANNER, WELCOME_INTRO } from '@shared/disclaimers';
import { CURRENT_CONSENT_VERSION } from '@shared/consent-version';
import { Colors, Fonts } from '@/constants/theme';

export default function HomeScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }}>
      <View style={{ flex: 1, padding: 20, gap: 16 }}>
        <View style={{ backgroundColor: Colors.sidebarBg, borderRadius: 12, padding: 14 }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            {AI_DISCLOSURE_BANNER}
          </Text>
        </View>

        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 24, color: Colors.textPrimary }}>
          WondrChat
        </Text>
        <Text style={{ color: Colors.textSecondary, fontSize: 15, lineHeight: 22 }}>
          {WELCOME_INTRO}
        </Text>

        <View style={{ marginTop: 'auto', paddingTop: 16, borderTopWidth: 1, borderTopColor: Colors.border }}>
          <Text style={{ color: Colors.textMuted, fontSize: 11 }}>
            Phase 0 scaffold · consent version {CURRENT_CONSENT_VERSION}
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}
