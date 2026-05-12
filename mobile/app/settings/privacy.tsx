import { Stack } from 'expo-router';
import { Linking, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { CONTACT } from '@shared/disclaimers';
import { CURRENT_CONSENT_VERSION } from '@shared/consent-version';

export default function PrivacyPolicy() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Privacy Policy' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 14 }}>
        <View
          style={{
            padding: 12,
            borderRadius: Radius.md,
            backgroundColor: Colors.warningBg,
          }}>
          <Text style={{ color: Colors.warning, fontSize: 12, lineHeight: 18 }}>
            DRAFT — ATTORNEY REVIEW REQUIRED. The full, current Privacy Policy lives on the web at
            wondrlinkfoundation.org/privacy.
          </Text>
        </View>

        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 21 }}>
          Effective Date: May 2026 · Version: {CURRENT_CONSENT_VERSION}
        </Text>

        <Section title="Service availability">
          WondrChat is available to adults (18+) in the United States. It is not currently
          available to residents of Illinois or Nevada due to state regulations that govern
          AI-delivered mental and behavioral health services.
        </Section>

        <Section title="What we collect">
          Cancer-related profile data you provide, your symptom and screening responses, your chat
          messages, your ZIP code (for trial search), and your account email + state.
        </Section>

        <Section title="What we don't do">
          We don't sell your data. We don't use it for advertising. We don't share it with
          insurers, employers, data brokers, or marketing companies.
        </Section>

        <Section title="AI processing">
          Your queries are sent to Together AI and Groq for inference. We apply a de-identification
          step before transmission to remove names, dates of birth, addresses, and other directly
          identifying information.
        </Section>

        <Section title="Your rights">
          You can access, correct, delete, or withdraw consent for your data at any time. Email
          {' '}{CONTACT.privacy} or use Delete Account in Settings. We respond within 45 days.
        </Section>

        <Section title="Global Privacy Control (GPC)">
          We honor browser-level GPC signals where they're set.
        </Section>

        <Button
          label="View the full policy on the web"
          variant="secondary"
          fullWidth
          onPress={() => Linking.openURL(`${CONTACT.website}/privacy`).catch(() => {})}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 4 }}>
      <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
        {title}
      </Text>
      <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 20 }}>{children}</Text>
    </View>
  );
}
