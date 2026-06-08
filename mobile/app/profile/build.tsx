import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Check, ChevronLeft, ChevronRight, Plus, X } from 'lucide-react-native';
import { useMemo, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { uploadProfile } from '@/lib/api/care';
import { ApiError, extractErrorMessage } from '@/lib/api/client';
import { useProfile } from '@/hooks/useCare';

type Sex = 'Male' | 'Female' | 'Other';

const ECOG = [
  { value: '0', title: 'Fully active', desc: 'No restrictions' },
  { value: '1', title: 'Light activity', desc: 'Can do light work' },
  { value: '2', title: 'Up 50%+', desc: 'Resting < half the day' },
  { value: '3', title: 'Resting 50%+', desc: 'In bed/chair > half the day' },
  { value: '4', title: 'Bedridden', desc: 'Completely confined' },
];

const STAGES = [
  { value: 'Stage I', desc: 'Early — in colon wall only' },
  { value: 'Stage II', desc: 'Grown through colon wall' },
  { value: 'Stage III', desc: 'Spread to lymph nodes' },
  { value: 'Stage IV', desc: 'Spread to other organs' },
  { value: 'Unknown', desc: "I don't know my stage" },
];

const HISTOLOGY = [
  { value: 'adenocarcinoma-nos', label: 'Adenocarcinoma (most common)' },
  { value: 'mucinous-adenocarcinoma', label: 'Mucinous adenocarcinoma' },
  { value: 'signet-ring-cell', label: 'Signet-ring cell' },
  { value: 'medullary-carcinoma', label: 'Medullary carcinoma' },
  { value: 'neuroendocrine-tumor', label: 'Neuroendocrine tumor' },
  { value: 'neuroendocrine-carcinoma', label: 'Neuroendocrine carcinoma' },
  { value: 'squamous-cell-carcinoma', label: 'Squamous cell carcinoma' },
  { value: 'gist', label: 'GIST' },
  { value: 'unknown', label: "I don't know" },
];

const COMORBIDITIES = [
  'Hypertension',
  'Type 2 diabetes',
  'Heart disease',
  'Kidney disease',
  'Liver disease',
  'COPD/Lung disease',
  'Obesity',
  'Arthritis',
];

interface BiomarkerDef {
  key: string;
  label: string;
  options: string[];
}

const ESSENTIAL_BIOMARKERS: BiomarkerDef[] = [
  { key: 'MSI', label: 'MSI', options: ['MSI-H', 'MSI-L', 'MSS', 'Unknown'] },
  { key: 'MMR', label: 'MMR', options: ['dMMR', 'pMMR', 'Unknown'] },
  { key: 'KRAS', label: 'KRAS', options: ['Wild-type', 'Mutant', 'Unknown'] },
  { key: 'NRAS', label: 'NRAS', options: ['Wild-type', 'Mutant', 'Unknown'] },
  { key: 'BRAF', label: 'BRAF', options: ['Wild-type', 'V600E', 'Other mutation', 'Unknown'] },
  { key: 'HER2', label: 'HER2', options: ['Positive', 'Negative', 'Unknown'] },
];

const EXTENDED_BIOMARKERS: BiomarkerDef[] = [
  { key: 'DPYD', label: 'DPYD', options: ['Normal', 'Partial deficiency', 'Complete deficiency', 'Not tested'] },
  { key: 'UGT1A1', label: 'UGT1A1', options: ['*1/*1', '*1/*28', '*28/*28', 'Not tested'] },
  { key: 'NTRK', label: 'NTRK', options: ['Positive', 'Negative', 'Not tested'] },
  { key: 'PIK3CA', label: 'PIK3CA', options: ['Wild-type', 'Mutant', 'Not tested'] },
  { key: 'TMB', label: 'TMB', options: ['High (≥10)', 'Low (<10)', 'Not tested'] },
  { key: 'PD-L1', label: 'PD-L1', options: ['Positive', 'Negative', 'Not tested'] },
];

const TREATMENT_REGIMENS: Record<string, string[]> = {
  Chemotherapy: [
    'FOLFOX',
    'FOLFIRI',
    'CAPOX',
    'FOLFOXIRI',
    '5-Fluorouracil (5-FU)',
    'Capecitabine',
    'Oxaliplatin',
    'Irinotecan',
    'Trifluridine/Tipiracil (Lonsurf)',
    'Other',
  ],
  Immunotherapy: [
    'Pembrolizumab (Keytruda)',
    'Nivolumab (Opdivo)',
    'Ipilimumab (Yervoy)',
    'Dostarlimab (Jemperli)',
    'Other',
  ],
  'Targeted Therapy': [
    'Bevacizumab (Avastin)',
    'Cetuximab (Erbitux)',
    'Panitumumab (Vectibix)',
    'Regorafenib (Stivarga)',
    'Encorafenib (Braftovi)',
    'Sotorasib (Lumakras)',
    'Other',
  ],
  Surgery: [
    'Polypectomy',
    'Local excision',
    'Partial colectomy',
    'Total colectomy',
    'Laparoscopic surgery',
    'Robotic surgery',
    'Metastasectomy',
    'Colostomy',
    'Ileostomy',
    'Other',
  ],
  'Radiation Therapy': [
    'External beam radiation (EBRT)',
    'Stereotactic body radiation (SBRT)',
    'Brachytherapy',
    'Proton beam therapy',
    'Other',
  ],
  'Other/Investigational': ['Clinical trial', 'Investigational drug', 'Other'],
};

const TREATMENT_LINES = ['1st line', '2nd line', '3rd+ line', 'Neoadjuvant', 'Adjuvant', 'Palliative'];
const TREATMENT_STATUSES = ['active', 'completed', 'on hold', 'planned'];

const SIDE_EFFECTS = [
  'Fatigue',
  'Nausea',
  'Neuropathy',
  'Diarrhea',
  'Constipation',
  'Mouth sores',
  'Hair thinning',
  'Skin rash',
  'Loss of appetite',
  'Hand-foot syndrome',
  'Low blood counts',
];

const SYMPTOMS = [
  'Fatigue',
  'Pain',
  'Nausea',
  'Loss of appetite',
  'Weight changes',
  'Sleep problems',
  'Anxiety',
  'Depression',
  'Constipation',
  'Diarrhea',
];

interface TreatmentInput {
  category: string;
  regimen: string;
  line: string;
  status: string;
  sideEffects: string[];
}

interface FormState {
  firstName: string;
  age: string;
  sex: Sex | '';
  zipCode: string;
  ecog: string;
  comorbidities: string[];
  allergies: string;
  stage: string;
  histology: string;
  biomarkers: Record<string, string>;
  treatments: TreatmentInput[];
  symptoms: string[];
}

const EMPTY_TREATMENT: TreatmentInput = {
  category: '',
  regimen: '',
  line: '1st line',
  status: 'active',
  sideEffects: [],
};

function readInitial(loaded: unknown): FormState {
  const p = (loaded as Record<string, unknown>) ?? {};
  const patient = (p.patient as Record<string, unknown>) ?? {};
  const dx = (p.primaryDiagnosis as Record<string, unknown>) ?? {};
  const bio = (dx.biomarkers as Record<string, string>) ?? {};
  const treatments = (p.treatments as Record<string, unknown>[]) ?? [];
  const symptoms = (p.symptoms as string[]) ?? [];
  const comorbidities = (patient.comorbidities as string[]) ?? [];
  return {
    firstName: (patient.firstName as string) ?? '',
    age: patient.age != null ? String(patient.age) : '',
    sex: ((patient.sex as Sex) ?? '') as Sex | '',
    zipCode: (patient.zipCode as string) ?? '',
    ecog: (patient.ecog as string) ?? '',
    comorbidities,
    allergies: (patient.allergies as string) ?? '',
    stage: (dx.stage as string) ?? '',
    histology: (dx.histology as string) ?? 'adenocarcinoma-nos',
    biomarkers: bio,
    treatments: treatments.length
      ? treatments.map((t) => ({
          category: (t.category as string) ?? '',
          regimen: (t.regimen as string) ?? '',
          line: (t.line as string) ?? '1st line',
          status: (t.status as string) ?? 'active',
          sideEffects: ((t.toxicities as { event: string }[]) ?? []).map((x) => x.event),
        }))
      : [],
    symptoms,
  };
}

const TOTAL_STEPS = 6;

export default function BuildProfileScreen() {
  const profile = useProfile();
  const qc = useQueryClient();
  const initial = useMemo(() => readInitial(profile.data?.profile), [profile.data?.profile]);
  const [state, setState] = useState<FormState>(initial);
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setState((s) => ({ ...s, [key]: value }));

  const canAdvance = (() => {
    if (step === 0) {
      return state.firstName.trim().length >= 2 && !!state.sex;
    }
    if (step === 1) {
      return !!state.stage && !!state.histology;
    }
    return true;
  })();

  const next = () => {
    if (step < TOTAL_STEPS - 1) setStep(step + 1);
  };
  const back = () => {
    if (step > 0) setStep(step - 1);
    else router.back();
  };

  const save = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        patient: {
          firstName: state.firstName.trim(),
          age: state.age ? Number(state.age) : undefined,
          sex: state.sex || undefined,
          zipCode: state.zipCode || undefined,
          ecog: state.ecog || undefined,
          comorbidities: state.comorbidities,
          allergies: state.allergies || undefined,
        },
        primaryDiagnosis: {
          site: 'colon',
          histology: state.histology,
          stage: state.stage,
          biomarkers: state.biomarkers,
        },
        treatments: state.treatments
          .filter((t) => t.category && t.regimen)
          .map((t) => ({
            category: t.category,
            regimen: t.regimen,
            line: t.line,
            status: t.status,
            toxicities: t.sideEffects.map((event) => ({ event })),
          })),
        symptoms: state.symptoms,
      };
      await uploadProfile(payload);
      await qc.invalidateQueries({ queryKey: ['profile'] });
      await qc.invalidateQueries({ queryKey: ['hero'] });
      await qc.invalidateQueries({ queryKey: ['care_snapshot'] });
      router.replace('/profile');
    } catch (e) {
      const fallback = e instanceof ApiError ? `Could not save (${e.status})` : 'Could not save.';
      setError(
        e instanceof ApiError
          ? extractErrorMessage(e.body, fallback)
          : extractErrorMessage(e, fallback),
      );
    } finally {
      setSubmitting(false);
    }
  };

  const stepTitles = ['Basics', 'Diagnosis', 'Health', 'Biomarkers', 'Treatments', 'Symptoms'];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <View style={{ paddingHorizontal: 20, paddingTop: 10, gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ color: Colors.textMuted, fontSize: 12, fontFamily: Fonts.sansMedium }}>
              STEP {step + 1} OF {TOTAL_STEPS}
            </Text>
            <Text style={{ color: Colors.textMuted, fontSize: 12 }}>· {stepTitles[step]}</Text>
          </View>
          <ProgressBar fraction={(step + 1) / TOTAL_STEPS} />
        </View>

        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 20, gap: 18, paddingBottom: 24 }}
          keyboardShouldPersistTaps="handled">
          {step === 0 && <StepBasics state={state} update={update} />}
          {step === 1 && <StepDiagnosis state={state} update={update} />}
          {step === 2 && <StepHealth state={state} update={update} />}
          {step === 3 && <StepBiomarkers state={state} update={update} />}
          {step === 4 && <StepTreatments state={state} update={update} />}
          {step === 5 && <StepSymptoms state={state} update={update} />}

          {error && (
            <Text style={{ color: Colors.danger, fontSize: 13, lineHeight: 18 }}>{error}</Text>
          )}
        </ScrollView>

        <View
          style={{
            padding: 16,
            paddingBottom: Platform.OS === 'ios' ? 24 : 16,
            borderTopWidth: 1,
            borderTopColor: Colors.border,
            backgroundColor: Colors.surface,
            gap: 8,
          }}>
          {step < TOTAL_STEPS - 1 ? (
            <Button
              label="Next"
              size="lg"
              fullWidth
              disabled={!canAdvance}
              trailingIcon={
                <ChevronRight size={18} color={canAdvance ? Colors.surface : Colors.textMuted} />
              }
              onPress={next}
            />
          ) : (
            <Button
              label="Save profile"
              size="lg"
              fullWidth
              loading={submitting}
              leadingIcon={<Check size={18} color={Colors.surface} />}
              onPress={save}
            />
          )}
          <Button
            label={step === 0 ? 'Cancel' : 'Back'}
            variant="ghost"
            fullWidth
            leadingIcon={
              step === 0 ? undefined : <ChevronLeft size={16} color={Colors.primary} />
            }
            onPress={back}
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function ProgressBar({ fraction }: { fraction: number }) {
  return (
    <View
      style={{ height: 4, borderRadius: 2, backgroundColor: Colors.border, overflow: 'hidden' }}>
      <View
        style={{
          width: `${Math.max(0, Math.min(1, fraction)) * 100}%`,
          height: '100%',
          backgroundColor: Colors.primary,
        }}
      />
    </View>
  );
}

interface StepProps {
  state: FormState;
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
}

function StepBasics({ state, update }: StepProps) {
  return (
    <>
      <Hint title="Basics" body="A few details so WondrChat can address you and gauge fit for trials." />
      <Field label="First name">
        <Input
          value={state.firstName}
          onChangeText={(v) => update('firstName', v)}
          placeholder="First name"
          autoCapitalize="words"
        />
      </Field>
      <Field label="Age (optional)">
        <Input
          value={state.age}
          onChangeText={(v) => update('age', v.replace(/[^0-9]/g, ''))}
          placeholder="e.g. 58"
          keyboardType="number-pad"
        />
      </Field>
      <Field label="Sex">
        <SegmentedChoice
          value={state.sex}
          options={[
            { value: 'Male', label: 'Male' },
            { value: 'Female', label: 'Female' },
            { value: 'Other', label: 'Other' },
          ]}
          onChange={(v) => update('sex', v as Sex)}
        />
      </Field>
    </>
  );
}

function StepDiagnosis({ state, update }: StepProps) {
  return (
    <>
      <Hint title="Diagnosis" body="Your cancer stage and histology shape what evidence we surface." />
      <Field label="Stage">
        <View style={{ gap: 8 }}>
          {STAGES.map((s) => (
            <ChoiceCard
              key={s.value}
              selected={state.stage === s.value}
              title={s.value}
              desc={s.desc}
              onPress={() => update('stage', s.value)}
            />
          ))}
        </View>
      </Field>
      <Field label="Histology (cancer type)">
        <Select
          value={state.histology}
          onChange={(v) => update('histology', v)}
          options={HISTOLOGY}
          placeholder="Select histology…"
        />
      </Field>
    </>
  );
}

function StepHealth({ state, update }: StepProps) {
  return (
    <>
      <Hint title="Your overall health" body="ECOG and comorbidities help match trial eligibility and flag interactions." />
      <Field label="ECOG performance status">
        <View style={{ gap: 8 }}>
          {ECOG.map((e) => (
            <ChoiceCard
              key={e.value}
              selected={state.ecog === e.value}
              title={`ECOG ${e.value} · ${e.title}`}
              desc={e.desc}
              onPress={() => update('ecog', e.value)}
            />
          ))}
        </View>
      </Field>
      <Field label="ZIP code (optional)">
        <Input
          value={state.zipCode}
          onChangeText={(v) => update('zipCode', v.replace(/[^0-9-]/g, '').slice(0, 10))}
          placeholder="e.g. 10001"
          keyboardType="number-pad"
        />
      </Field>
      <Field label="Other health conditions (optional)">
        <ChipMultiSelect
          options={COMORBIDITIES}
          selected={state.comorbidities}
          onChange={(next) => update('comorbidities', next)}
        />
      </Field>
      <Field label="Allergies (optional)">
        <Input
          value={state.allergies}
          onChangeText={(v) => update('allergies', v)}
          placeholder="e.g. penicillin, sulfa drugs"
        />
      </Field>
    </>
  );
}

function StepBiomarkers({ state, update }: StepProps) {
  const [showMore, setShowMore] = useState(false);
  const updateBio = (key: string, value: string) => {
    update('biomarkers', { ...state.biomarkers, [key]: value });
  };
  return (
    <>
      <Hint
        title="Biomarkers"
        body="Find these on your pathology or molecular-testing report, or ask your oncologist. Leave any blank if you're not sure."
      />
      {ESSENTIAL_BIOMARKERS.map((b) => (
        <Field key={b.key} label={b.label}>
          <SegmentedChoice
            value={state.biomarkers[b.key] ?? ''}
            options={b.options.map((o) => ({ value: o, label: o }))}
            onChange={(v) => updateBio(b.key, v)}
            allowDeselect
          />
        </Field>
      ))}
      <Pressable
        onPress={() => setShowMore((v) => !v)}
        accessibilityRole="button"
        style={({ pressed }) => ({
          paddingVertical: 10,
          paddingHorizontal: 12,
          borderRadius: Radius.md,
          backgroundColor: pressed ? Colors.surfaceMuted : Colors.sidebarBg,
          alignSelf: 'flex-start',
        })}>
        <Text style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: 13 }}>
          {showMore ? 'Hide additional biomarkers' : 'Add more biomarkers (DPYD, NTRK, TMB…)'}
        </Text>
      </Pressable>
      {showMore &&
        EXTENDED_BIOMARKERS.map((b) => (
          <Field key={b.key} label={b.label}>
            <SegmentedChoice
              value={state.biomarkers[b.key] ?? ''}
              options={b.options.map((o) => ({ value: o, label: o }))}
              onChange={(v) => updateBio(b.key, v)}
              allowDeselect
            />
          </Field>
        ))}
    </>
  );
}

function StepTreatments({ state, update }: StepProps) {
  const add = () => update('treatments', [...state.treatments, { ...EMPTY_TREATMENT }]);
  const remove = (i: number) =>
    update(
      'treatments',
      state.treatments.filter((_, idx) => idx !== i),
    );
  const change = (i: number, patch: Partial<TreatmentInput>) => {
    const next = state.treatments.map((t, idx) => (idx === i ? { ...t, ...patch } : t));
    update('treatments', next);
  };
  return (
    <>
      <Hint
        title="Treatments"
        body="Add each treatment you've had or are receiving. You can leave this blank if none apply yet."
      />
      {state.treatments.map((t, i) => (
        <TreatmentCard
          key={i}
          treatment={t}
          onChange={(patch) => change(i, patch)}
          onRemove={() => remove(i)}
        />
      ))}
      <Button
        label="Add a treatment"
        variant="secondary"
        fullWidth
        leadingIcon={<Plus size={16} color={Colors.primary} />}
        onPress={add}
      />
    </>
  );
}

function TreatmentCard({
  treatment,
  onChange,
  onRemove,
}: {
  treatment: TreatmentInput;
  onChange: (patch: Partial<TreatmentInput>) => void;
  onRemove: () => void;
}) {
  const regimens = treatment.category ? TREATMENT_REGIMENS[treatment.category] ?? [] : [];
  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        padding: 14,
        gap: 12,
        backgroundColor: Colors.surface,
      }}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <Text
          style={{
            flex: 1,
            color: Colors.textPrimary,
            fontFamily: Fonts.sansSemiBold,
            fontSize: 14,
          }}>
          {treatment.regimen || treatment.category || 'New treatment'}
        </Text>
        <Pressable
          onPress={onRemove}
          accessibilityRole="button"
          accessibilityLabel="Remove this treatment"
          hitSlop={8}
          style={({ pressed }) => ({
            padding: 6,
            borderRadius: 8,
            backgroundColor: pressed ? Colors.surfaceMuted : 'transparent',
          })}>
          <X size={18} color={Colors.textMuted} />
        </Pressable>
      </View>
      <Field label="Type">
        <Select
          value={treatment.category}
          onChange={(v) => onChange({ category: v, regimen: '' })}
          options={Object.keys(TREATMENT_REGIMENS).map((c) => ({ value: c, label: c }))}
          placeholder="Select type…"
        />
      </Field>
      {treatment.category ? (
        <Field label="Regimen">
          <Select
            value={treatment.regimen}
            onChange={(v) => onChange({ regimen: v })}
            options={regimens.map((r) => ({ value: r, label: r }))}
            placeholder="Select regimen…"
          />
        </Field>
      ) : null}
      <Field label="Line">
        <Select
          value={treatment.line}
          onChange={(v) => onChange({ line: v })}
          options={TREATMENT_LINES.map((l) => ({ value: l, label: l }))}
        />
      </Field>
      <Field label="Status">
        <SegmentedChoice
          value={treatment.status}
          options={TREATMENT_STATUSES.map((s) => ({ value: s, label: s }))}
          onChange={(v) => onChange({ status: v })}
        />
      </Field>
      <Field label="Side effects (optional)">
        <ChipMultiSelect
          options={SIDE_EFFECTS}
          selected={treatment.sideEffects}
          onChange={(next) => onChange({ sideEffects: next })}
        />
      </Field>
    </View>
  );
}

function StepSymptoms({ state, update }: StepProps) {
  return (
    <>
      <Hint
        title="Current symptoms"
        body="What you're feeling right now. WondrChat uses this to know when to flag something worth raising with your care team."
      />
      <ChipMultiSelect
        options={SYMPTOMS}
        selected={state.symptoms}
        onChange={(next) => update('symptoms', next)}
      />
    </>
  );
}

function Hint({ title, body }: { title: string; body: string }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ fontFamily: Fonts.serifBold, fontSize: 20, color: Colors.textPrimary }}>
        {title}
      </Text>
      <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>{body}</Text>
    </View>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 6 }}>
      <Text
        style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
        {label}
      </Text>
      {children}
    </View>
  );
}

function Input(props: React.ComponentProps<typeof TextInput>) {
  return (
    <TextInput
      {...props}
      placeholderTextColor={Colors.textMuted}
      style={[
        {
          borderWidth: 1,
          borderColor: Colors.border,
          backgroundColor: Colors.surface,
          borderRadius: Radius.md,
          paddingHorizontal: 14,
          paddingVertical: 12,
          color: Colors.textPrimary,
          fontSize: 15,
          fontFamily: Fonts.sans,
        },
        props.style,
      ]}
    />
  );
}

function ChoiceCard({
  selected,
  title,
  desc,
  onPress,
}: {
  selected: boolean;
  title: string;
  desc?: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      style={({ pressed }) => ({
        paddingHorizontal: 14,
        paddingVertical: 12,
        borderRadius: Radius.lg,
        borderWidth: selected ? 2 : 1,
        borderColor: selected ? Colors.primary : Colors.border,
        backgroundColor: selected
          ? Colors.primarySoft
          : pressed
            ? Colors.sidebarBg
            : Colors.surfaceMuted,
      })}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View
          style={{
            width: 22,
            height: 22,
            borderRadius: 11,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: selected ? Colors.primary : 'transparent',
            borderWidth: selected ? 0 : 1.5,
            borderColor: Colors.border,
          }}>
          {selected && <Check size={14} color={Colors.surface} strokeWidth={3} />}
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text
            style={{
              color: selected ? Colors.primary : Colors.textPrimary,
              fontFamily: Fonts.sansSemiBold,
              fontSize: 14,
            }}>
            {title}
          </Text>
          {desc ? (
            <Text
              style={{
                color: selected ? Colors.primary : Colors.textMuted,
                fontSize: 12,
                marginTop: 2,
              }}>
              {desc}
            </Text>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

function SegmentedChoice({
  value,
  options,
  onChange,
  allowDeselect,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  allowDeselect?: boolean;
}) {
  return (
    <View style={pillStyles.row}>
      {options.map((opt) => {
        const selected = value === opt.value;
        return (
          <View
            key={opt.value}
            style={[pillStyles.pill, selected && pillStyles.pillSelected]}>
            <View style={pillStyles.inner} pointerEvents="none">
              {selected && (
                <Check size={14} color={Colors.primary} strokeWidth={3} />
              )}
              <Text
                style={[pillStyles.label, selected && pillStyles.labelSelected]}>
                {opt.label}
              </Text>
            </View>
            <Pressable
              onPress={() => onChange(selected && allowDeselect ? '' : opt.value)}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              android_ripple={{ color: Colors.sidebarBg, borderless: false }}
              style={StyleSheet.absoluteFill}
            />
          </View>
        );
      })}
    </View>
  );
}

function ChipMultiSelect({
  options,
  selected,
  onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (opt: string) => {
    if (selected.includes(opt)) onChange(selected.filter((x) => x !== opt));
    else onChange([...selected, opt]);
  };
  return (
    <View style={{ gap: 8 }}>
      <Text style={pillStyles.helper}>Tap any that apply — you can pick several.</Text>
      <View style={pillStyles.row}>
        {options.map((opt) => {
          const isSel = selected.includes(opt);
          return (
            <View
              key={opt}
              style={[pillStyles.pill, isSel && pillStyles.pillSelected]}>
              <View style={pillStyles.inner} pointerEvents="none">
                {isSel ? (
                  <Check size={14} color={Colors.primary} strokeWidth={3} />
                ) : (
                  <Plus size={14} color={Colors.textMuted} strokeWidth={2.4} />
                )}
                <Text
                  style={[pillStyles.label, isSel && pillStyles.labelSelected]}>
                  {opt}
                </Text>
              </View>
              <Pressable
                onPress={() => toggle(opt)}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: isSel }}
                android_ripple={{ color: Colors.sidebarBg, borderless: false }}
                style={StyleSheet.absoluteFill}
              />
            </View>
          );
        })}
      </View>
    </View>
  );
}

const pillStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surfaceMuted,
    position: 'relative',
    overflow: 'hidden',
  },
  pillSelected: {
    borderWidth: 2,
    borderColor: Colors.primary,
    backgroundColor: Colors.primarySoft,
  },
  inner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  label: {
    fontFamily: Fonts.sansMedium,
    fontSize: 13,
    color: Colors.textPrimary,
  },
  labelSelected: {
    fontFamily: Fonts.sansSemiBold,
    color: Colors.primary,
  },
  helper: {
    fontSize: 12,
    color: Colors.textMuted,
    fontFamily: Fonts.sansMedium,
  },
});

