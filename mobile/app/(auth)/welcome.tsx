import { router } from 'expo-router';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts } from '@/constants/theme';
import { WELCOME_INTRO } from '@shared/disclaimers';

export default function Welcome() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }}>
      <View style={{ flex: 1, padding: 24, justifyContent: 'space-between' }}>
        <View style={{ flex: 1, justifyContent: 'center', gap: 16 }}>
          <Text
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.85}
            style={{
              fontFamily: Fonts.serifBold,
              fontSize: 30,
              color: Colors.textPrimary,
              lineHeight: 36,
            }}>
            Sage
          </Text>
          <Text style={{ fontSize: 15, lineHeight: 22, color: Colors.textSecondary }}>
            {WELCOME_INTRO}
          </Text>
        </View>

        <View style={{ gap: 12 }}>
          <Button
            label="Continue with phone"
            fullWidth
            size="lg"
            onPress={() => router.push('/(auth)/phone' as never)}
          />
          <Button
            label="Use email instead"
            variant="secondary"
            fullWidth
            size="lg"
            onPress={() => router.push('/(auth)/login')}
          />
          <Text
            onPress={() => router.push('/(auth)/register')}
            style={{
              textAlign: 'center',
              color: Colors.textMuted,
              fontSize: 13,
              paddingVertical: 4,
            }}>
            New here with email? Create an account
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}
