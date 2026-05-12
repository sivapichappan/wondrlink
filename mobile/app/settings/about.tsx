import { Stack } from 'expo-router';
import Constants from 'expo-constants';
import { Linking, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { CONTACT } from '@shared/disclaimers';
import { CURRENT_CONSENT_VERSION } from '@shared/consent-version';

export default function About() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'About' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 14 }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
          WondrChat
        </Text>
        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
          A colon cancer informational guide built by the WondrLink Foundation. WondrChat is
          designed to help patients and caregivers understand diagnosis, treatment options,
          screenings, and resources — in plain language.
        </Text>

        <View
          style={{
            padding: 12,
            backgroundColor: Colors.sidebarBg,
            borderRadius: Radius.md,
            gap: 4,
          }}>
          <Row label="App version" value={Constants.expoConfig?.version ?? '—'} />
          <Row label="iOS build" value={String(Constants.expoConfig?.ios?.buildNumber ?? '—')} />
          <Row label="Android version code" value={String(Constants.expoConfig?.android?.versionCode ?? '—')} />
          <Row label="Consent version" value={CURRENT_CONSENT_VERSION} />
        </View>

        <Button
          label="Visit wondrlinkfoundation.org"
          variant="secondary"
          fullWidth
          onPress={() => Linking.openURL(CONTACT.website).catch(() => {})}
        />
        <Button
          label="Email privacy@wondrlinkfoundation.org"
          variant="ghost"
          fullWidth
          onPress={() => Linking.openURL(`mailto:${CONTACT.privacy}`).catch(() => {})}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 }}>
      <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>{label}</Text>
      <Text style={{ color: Colors.textPrimary, fontSize: 12, fontFamily: Fonts.sansSemiBold }}>
        {value}
      </Text>
    </View>
  );
}
