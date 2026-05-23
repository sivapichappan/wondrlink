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
          AI-delivered mental and behavioral health services, nor to residents of the EU, EEA,
          UK, or Switzerland while we complete the compliance work required to serve those regions.
        </Section>

        <Section title="What we collect">
          Cancer-related profile data you provide, your symptom and screening responses, your chat
          messages, your ZIP code (for trial search), and your account email + state. We verify
          your age at signup via date of birth; the raw date is not stored — only the derived age
          band (e.g. 35–44).
        </Section>

        <Section title="What we don't do">
          We don't sell your data. We don't use it for advertising. We don't share it with
          insurers, employers, data brokers, or marketing companies.
        </Section>

        <Section title="AI processing">
          Your queries are sent to Together AI and Groq for inference. We apply a de-identification
          step before transmission to remove names, dates of birth, addresses, phone numbers,
          emails, SSNs, MRNs, insurance IDs, ZIP codes, and other directly identifying information.
        </Section>

        <Section title="Data retention">
          Our retention periods are:
          {'\n'}• Active account data — retained while your account is active.
          {'\n'}• On account deletion — hard delete from our active database within 7 days;
          Supabase backups (point-in-time recovery) complete purge within 90 days.
          {'\n'}• Rate-limit records — purged after 24 hours.
          {'\n'}• Consent withdrawal logs — retained 6 years as the auditable record of your
          consent history (the only data that survives an account deletion, kept for MHMDA / CCPA
          audit defense only; we cannot use it for any other purpose).
          {'\n'}• Anonymous aggregated usage statistics — retained indefinitely.
          {'\n'}• Sub-processor retention follows each vendor's policy.
        </Section>

        <Section title="Your rights">
          You can access, correct, delete, or withdraw consent for your data at any time. Email
          {' '}{CONTACT.privacy} or use Settings → Consent Management (per-consent toggles) or
          Settings → Delete Account (nuke everything). We respond within 45 days, with one
          45-day extension permitted.
        </Section>

        <Section title="Your state privacy rights">
          Residents of the following states have rights of access, deletion, correction, and
          (where applicable) opt-out of targeted advertising under their state's comprehensive
          privacy law: California (CCPA / CPRA — plus the Limit Use of Sensitive PI affordance
          in Settings), Virginia (VCDPA), Colorado (CPA), Connecticut (CTDPA), Utah (UCPA),
          Iowa (ICDPA), Indiana, Tennessee (TIPA), Texas (TDPSA), Oregon (OCPA), Montana (MCDPA),
          Delaware (DPDPA), New Hampshire (NHDPA), New Jersey (NJDPA), Kentucky (KCDPA),
          Rhode Island (RIDTPPA), Minnesota (MCDPA), Maryland (MODPA), Nebraska (NDPA).
          {'\n\n'}Washington residents: separate rights under the My Health My Data Act
          are described in the Consumer Health Data Privacy Notice (Settings → Consumer
          Health Data Privacy Notice).
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
