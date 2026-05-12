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
            style={{
              fontFamily: Fonts.serifBold,
              fontSize: 32,
              color: Colors.textPrimary,
              lineHeight: 38,
            }}>
            WondrChat
          </Text>
          <Text style={{ fontSize: 15, lineHeight: 22, color: Colors.textSecondary }}>
            {WELCOME_INTRO}
          </Text>
        </View>

        <View style={{ gap: 12 }}>
          <Button
            label="Create account"
            fullWidth
            size="lg"
            onPress={() => router.push('/(auth)/register')}
          />
          <Button
            label="Log in"
            variant="secondary"
            fullWidth
            size="lg"
            onPress={() => router.push('/(auth)/login')}
          />
        </View>
      </View>
    </SafeAreaView>
  );
}
