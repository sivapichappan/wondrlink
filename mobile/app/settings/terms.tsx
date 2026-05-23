import { Stack } from 'expo-router';
import { Linking, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { CONTACT } from '@shared/disclaimers';

export default function Terms() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Terms of Use' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 14 }}>
        <View
          style={{
            padding: 12,
            borderRadius: Radius.md,
            backgroundColor: Colors.warningBg,
          }}>
          <Text style={{ color: Colors.warning, fontSize: 12, lineHeight: 18 }}>
            DRAFT — ATTORNEY REVIEW REQUIRED. The current Terms of Use live at
            wondrlinkfoundation.org/terms.
          </Text>
        </View>

        <Section title="Not medical advice">
          WondrChat provides general educational information about colon cancer. It is not a
          substitute for professional medical advice, diagnosis, or treatment. Always consult your
          oncologist or qualified healthcare provider with questions about your medical condition.
        </Section>

        <Section title="No diagnoses, no prescriptions">
          WondrChat does not provide diagnoses, prescriptions, or treatment plans. AI-generated
          responses may contain errors — verify all information with your care team before acting
          on it.
        </Section>

        <Section title="Emergencies">
          If you are experiencing a medical emergency, call 911 immediately. WondrChat is not
          equipped to handle emergencies.
        </Section>

        <Section title="Eligible users">
          To use WondrChat you must be at least 18 years of age. We verify your age via date of
          birth at signup; we do not store the raw date, only the derived age band (e.g. 35–44).
          WondrChat is not currently available to residents of Illinois or Nevada due to state
          regulations governing AI in mental and behavioral health, nor to residents of the EU,
          EEA, UK, or Switzerland while we complete the compliance work required to serve those
          regions. By creating an account you confirm you meet these eligibility requirements.
        </Section>

        <Section title="Acceptable use">
          You agree not to attempt to misuse the service, scrape it, reverse-engineer it, or use
          it for purposes other than personal informational use.
        </Section>

        <Section title="Termination">
          You may delete your account at any time from Settings. We may terminate accounts that
          violate these Terms.
        </Section>

        <Button
          label="View the full terms on the web"
          variant="secondary"
          fullWidth
          onPress={() => Linking.openURL(`${CONTACT.website}/terms`).catch(() => {})}
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
