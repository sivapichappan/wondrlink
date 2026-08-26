import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts } from '@/constants/theme';
import { APP_NAME } from '@shared/branding';
import { WELCOME_INTRO } from '@shared/disclaimers';

/** Set when someone enters through the "For oncologists" door. */
export const REVIEWER_INTENT_KEY = 'sage:reviewer_intent';

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
            {APP_NAME}
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
          {/* The oncologist door (mockup 01). It was a full fork screen
              asking every patient which kind of account they wanted; it is
              a footer link now, and the patient app never mentions
              oncologists again. The intent is remembered so the gate can
              send a clinician past the PATIENT consent, which is what the
              fork existed to prevent them from being shown. */}
          <Text
            onPress={() => {
              AsyncStorage.setItem(REVIEWER_INTENT_KEY, '1').catch(() => {});
              router.push('/(auth)/register');
            }}
            accessibilityRole="link"
            style={{
              textAlign: 'center',
              color: Colors.textMuted,
              fontSize: 13,
              paddingVertical: 6,
              textDecorationLine: 'underline',
            }}>
            For oncologists
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}
