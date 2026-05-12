import { router } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts } from '@/constants/theme';
import { CONTACT } from '@shared/disclaimers';
import { CURRENT_CONSENT_VERSION } from '@shared/consent-version';

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <View style={{ gap: 6 }}>
    <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 15, color: Colors.textPrimary }}>{title}</Text>
    {children}
  </View>
);
const P = ({ children }: { children: React.ReactNode }) => (
  <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>{children}</Text>
);

export default function Disclaimer() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        <View
          style={{
            backgroundColor: '#FEF3C7',
            borderRadius: 10,
            padding: 12,
          }}>
          <Text style={{ color: '#92400E', fontSize: 12, lineHeight: 18 }}>
            DRAFT — ATTORNEY REVIEW REQUIRED. Prepared in good faith using the Washington
            My Health My Data Act (MHMDA) as a template.
          </Text>
        </View>

        <P>Effective Date: May 2026 · Version: {CURRENT_CONSENT_VERSION}</P>

        <Section title="About this Notice">
          <P>
            This Notice describes how WondrLink Foundation ("WondrLink", "we", "us") collects,
            uses, shares, and protects consumer health data. It is provided separately from our
            general Privacy Policy in compliance with MHMDA. Washington residents have specific
            rights under MHMDA; we extend those rights to all WondrLink users regardless of state.
          </P>
        </Section>

        <Section title="Categories of Consumer Health Data We Collect">
          <P>
            • Cancer-related information you provide (diagnosis, stage, treatments, biomarkers,
            comorbidities){'\n'}
            • Symptom reports and check-ins (PRO-CTCAE-aligned){'\n'}
            • Self-administered screening responses (PHQ-9, GAD-7, PSS-10, ISI, PREMM5){'\n'}
            • Questions you ask in the chat interface{'\n'}
            • ZIP code (for finding clinical trials in your area){'\n'}
            • Account information (email, age confirmation, state of residence)
          </P>
        </Section>

        <Section title="How We Use Your Consumer Health Data">
          <P>
            • To generate personalized educational responses about colon cancer{'\n'}
            • To match you against clinical-trial eligibility criteria you ask about{'\n'}
            • To track your screening history so you can share trends with your care team{'\n'}
            • To improve the service in aggregate using de-identified data only
          </P>
          <P>
            We do <Text style={{ fontFamily: Fonts.sansSemiBold }}>not</Text> sell your consumer
            health data. We do not use it for advertising. We do not share it with insurers,
            employers, data brokers, or marketing companies.
          </P>
        </Section>

        <Section title="Sub-Processors">
          <P>
            • Supabase, Inc. — database hosting{'\n'}
            • Together AI — LLM inference (de-identified queries + retrieved excerpts){'\n'}
            • Groq, Inc. — LLM inference fallback (same scope as Together AI){'\n'}
            • Vercel, Inc. — application hosting (request metadata only){'\n'}
            • ClinicalTrials.gov (US NIH) — public records only
          </P>
          <P>
            Before sending your queries to an AI provider, we apply a de-identification step that
            removes names, dates of birth, addresses, and other directly identifying information.
          </P>
        </Section>

        <Section title="Your Rights">
          <P>
            You may confirm, access, correct, delete, or withdraw consent for your data at any
            time. Email {CONTACT.privacy} or use the "Delete Account" option in Settings.
            We will respond within 45 days. Appeals: {CONTACT.appeals}.
          </P>
        </Section>

        <Section title="Retention">
          <P>
            We retain your consumer health data while your account is active. On deletion, your
            data is removed from our primary database within 30 days. Sub-processor logs may
            persist beyond this window per their own retention policies.
          </P>
        </Section>

        <Section title="Changes to this Notice">
          <P>
            We will notify you of material changes by requiring re-acknowledgement on next login.
          </P>
        </Section>

        <Section title="Contact">
          <P>WondrLink Foundation — {CONTACT.privacy}</P>
        </Section>

        <View style={{ height: 12 }} />
        <Button label="I've read it — go back" variant="secondary" fullWidth onPress={() => router.back()} />
      </ScrollView>
    </SafeAreaView>
  );
}
