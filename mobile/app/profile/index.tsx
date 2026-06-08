import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import {
  Activity,
  Beaker,
  ChevronRight,
  ClipboardList,
  Edit3,
  Heart,
  Pill,
  Tag,
  User,
} from 'lucide-react-native';
import { Alert, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useProfile } from '@/hooks/useCare';
import { clearProfile } from '@/lib/api/care';

interface PatientObj {
  firstName?: string;
  name?: string;
  age?: number | string;
  sex?: string;
  zipCode?: string;
  ecog?: string;
  allergies?: string;
  comorbidities?: string[];
}

interface DiagnosisObj {
  histology?: string;
  stage?: string;
  biomarkers?: Record<string, string>;
}

interface Treatment {
  category?: string;
  regimen?: string;
  line?: string;
  status?: string;
  toxicities?: { event: string; grade?: string }[];
}

export default function ProfileViewScreen() {
  const profile = useProfile();
  const ack = useAcknowledgement();
  const qc = useQueryClient();

  const reset = () => {
    Alert.alert(
      'Reset your profile?',
      'This removes the personalized profile WondrChat uses. Your chat history is unaffected.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            await clearProfile();
            qc.invalidateQueries({ queryKey: ['profile'] });
            qc.invalidateQueries({ queryKey: ['hero'] });
          },
        },
      ],
    );
  };

  const p = profile.data?.profile as
    | {
        patient?: PatientObj;
        primaryDiagnosis?: DiagnosisObj;
        treatments?: Treatment[];
        symptoms?: string[];
      }
    | undefined;
  const patient = p?.patient ?? {};
  const dx = p?.primaryDiagnosis ?? {};
  const treatments = p?.treatments ?? [];
  const symptoms = p?.symptoms ?? [];

  if (!p) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
            Build your profile
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
            Adding your diagnosis, biomarkers, and treatments lets WondrChat give answers that are
            specific to your situation instead of generic. It only takes a few minutes and you can
            edit it any time.
          </Text>
          <Button
            label="Start"
            fullWidth
            size="lg"
            leadingIcon={<Edit3 size={18} color={Colors.surface} />}
            onPress={() => router.push('/profile/build')}
          />
        </ScrollView>
      </SafeAreaView>
    );
  }

  const name = patient.firstName || patient.name || 'Your profile';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16, paddingBottom: 40 }}>
        <View style={{ gap: 4 }}>
          <Text
            numberOfLines={1}
            ellipsizeMode="tail"
            style={{ fontFamily: Fonts.serifBold, fontSize: 24, color: Colors.textPrimary }}>
            {name}
          </Text>
          {profile.data?.patient_summary ? (
            <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
              {profile.data.patient_summary}
            </Text>
          ) : null}
        </View>

        <Button
          label="Edit profile"
          variant="secondary"
          fullWidth
          leadingIcon={<Edit3 size={16} color={Colors.primary} />}
          onPress={() => router.push('/profile/build')}
        />

        <Pressable
          onPress={() => router.push('/profile/cancer-switcher')}
          accessibilityRole="button"
          accessibilityLabel="Change cancer focus"
          style={({ pressed }) => ({
            borderRadius: Radius.lg,
            borderWidth: 1,
            borderColor: pressed ? Colors.primary : Colors.border,
            backgroundColor: pressed ? Colors.primarySoft : Colors.surfaceMuted,
          })}>
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              padding: 14,
            }}>
            <Tag size={18} color={Colors.primary} style={{ marginRight: 10 }} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text
                style={{
                  color: Colors.textPrimary,
                  fontFamily: Fonts.sansSemiBold,
                  fontSize: 14,
                }}>
                Cancer focus
              </Text>
              <Text
                numberOfLines={1}
                ellipsizeMode="tail"
                style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
                {ack.data?.cancer_display ?? 'Tap to set'}
              </Text>
            </View>
            <ChevronRight size={18} color={Colors.primary} style={{ marginLeft: 8 }} />
          </View>
        </Pressable>

        <Section title="About you" Icon={User}>
          <Row label="Age" value={patient.age != null ? String(patient.age) : '—'} />
          <Row label="Sex" value={patient.sex || '—'} />
          <Row label="ZIP code" value={patient.zipCode || '—'} />
          <Row label="ECOG status" value={patient.ecog ?? '—'} />
        </Section>

        <Section title="Diagnosis" Icon={Heart}>
          <Row label="Stage" value={dx.stage || '—'} />
          <Row label="Histology" value={dx.histology || '—'} />
        </Section>

        <Section title="Biomarkers" Icon={Beaker}>
          {dx.biomarkers && Object.keys(dx.biomarkers).length > 0 ? (
            Object.entries(dx.biomarkers).map(([k, v]) => (
              <Row key={k} label={k} value={v ?? '—'} />
            ))
          ) : (
            <Empty>No biomarkers recorded.</Empty>
          )}
        </Section>

        <Section title="Treatments" Icon={Pill}>
          {treatments.length > 0 ? (
            treatments.map((t, i) => (
              <View
                key={i}
                style={{
                  paddingVertical: 10,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: Colors.border,
                }}>
                <Text
                  style={{
                    color: Colors.textPrimary,
                    fontFamily: Fonts.sansSemiBold,
                    fontSize: 14,
                  }}>
                  {t.regimen || t.category || 'Treatment'}
                </Text>
                <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
                  {[t.category, t.line, t.status].filter(Boolean).join(' · ') || '—'}
                </Text>
                {t.toxicities && t.toxicities.length > 0 ? (
                  <Text style={{ color: Colors.textSecondary, fontSize: 12, marginTop: 4 }}>
                    Side effects: {t.toxicities.map((x) => x.event).join(', ')}
                  </Text>
                ) : null}
              </View>
            ))
          ) : (
            <Empty>No treatments recorded.</Empty>
          )}
        </Section>

        <Section title="Current symptoms" Icon={Activity}>
          {symptoms.length > 0 ? (
            <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
              {symptoms.join(', ')}
            </Text>
          ) : (
            <Empty>None reported.</Empty>
          )}
        </Section>

        {patient.allergies ? (
          <Section title="Allergies" Icon={ClipboardList}>
            <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
              {patient.allergies}
            </Text>
          </Section>
        ) : null}

        {patient.comorbidities && patient.comorbidities.length > 0 ? (
          <Section title="Other conditions" Icon={ClipboardList}>
            <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
              {patient.comorbidities.join(', ')}
            </Text>
          </Section>
        ) : null}

        <View style={{ height: 8 }} />
        <Button label="Reset profile" variant="danger" fullWidth onPress={reset} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({
  title,
  Icon,
  children,
}: {
  title: string;
  Icon: typeof User;
  children: React.ReactNode;
}) {
  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        overflow: 'hidden',
        backgroundColor: Colors.surface,
      }}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 14,
          paddingVertical: 10,
          borderBottomWidth: 1,
          borderBottomColor: Colors.border,
          backgroundColor: Colors.sidebarBg,
        }}>
        <Icon size={16} color={Colors.primary} style={{ marginRight: 8 }} />
        <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
          {title}
        </Text>
      </View>
      <View style={{ padding: 14, gap: 4 }}>{children}</View>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingVertical: 6,
      }}>
      <Text style={{ color: Colors.textMuted, fontSize: 13 }}>{label}</Text>
      <Text
        numberOfLines={1}
        ellipsizeMode="tail"
        style={{
          color: Colors.textPrimary,
          fontFamily: Fonts.sansMedium,
          fontSize: 14,
          maxWidth: '60%',
        }}>
        {value}
      </Text>
    </View>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <Text style={{ color: Colors.textMuted, fontSize: 13, fontStyle: 'italic' }}>{children}</Text>
  );
}
