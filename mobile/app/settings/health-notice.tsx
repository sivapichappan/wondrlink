import { Stack } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts } from '@/constants/theme';
import { CURRENT_CONSENT_VERSION } from '@shared/consent-version';
import { CONTACT } from '@shared/disclaimers';

/**
 * Consumer Health Data Privacy Notice — settings-tab entry point.
 *
 * Content mirrors app/(onboarding)/disclaimer.tsx (which shows the same notice
 * during signup). Keep the two in sync if legal copy changes.
 */
export default function HealthNotice() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Consumer Health Notice' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16, paddingBottom: 40 }}>
        <View
          style={{
            backgroundColor: Colors.warningBg,
            borderRadius: 10,
            padding: 12,
          }}>
          <Text style={{ color: Colors.warning, fontSize: 12, lineHeight: 18 }}>
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
            time. Use Settings → Consent Management to toggle any signup consent off without
            deleting your account; use Settings → Delete Account to remove everything. Email
            {' '}{CONTACT.privacy} for an access or correction request. We respond within 45
            days, with one 45-day extension permitted. Appeals: {CONTACT.appeals}.
          </P>
        </Section>

        <Section title="Retention">
          <P>
            • Active account data: retained while your account is active.{'\n'}
            • On account deletion: hard delete from our active database within 7 days; Supabase
            backups (point-in-time recovery) complete purge within 90 days.{'\n'}
            • Rate-limit records: purged after 24 hours.{'\n'}
            • Consent withdrawal logs: retained 6 years as the auditable record of your consent
            history (the only data that survives an account deletion, kept for MHMDA / CCPA
            audit defense; we cannot use it for any other purpose).{'\n'}
            • Anonymous aggregated usage statistics: retained indefinitely.{'\n'}
            • Sub-processor retention follows each vendor's own policy.
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
      </ScrollView>
    </SafeAreaView>
  );
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <View style={{ gap: 6 }}>
    <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 15, color: Colors.textPrimary }}>
      {title}
    </Text>
    {children}
  </View>
);

const P = ({ children }: { children: React.ReactNode }) => (
  <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>{children}</Text>
);
