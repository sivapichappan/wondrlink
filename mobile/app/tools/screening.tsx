import { Stack, router, useLocalSearchParams } from 'expo-router';
import { Check, ChevronLeft, ChevronRight, Phone } from 'lucide-react-native';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Linking,
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { saveScreening } from '@/lib/api/tools';
import type { ScreeningCrisisResources, ScreeningInstrument } from '@shared/types';

interface ScaleOption {
  value: number;
  label: string;
}

interface SeverityBand {
  max: number;
  label: string;
  blurb: string;
}

interface InstrumentDef {
  key: ScreeningInstrument;
  title: string;
  shortTitle: string;
  intro: string;
  questions: string[];
  scale: ScaleOption[];
  severity: SeverityBand[];
  reverseScored?: number[];
}

const INSTRUMENTS: Record<ScreeningInstrument, InstrumentDef> = {
  PHQ9: {
    key: 'PHQ9',
    title: 'Depression (PHQ-9)',
    shortTitle: 'PHQ-9',
    intro: 'Over the last 2 weeks, how often have you been bothered by any of the following?',
    questions: [
      'Little interest or pleasure in doing things',
      'Feeling down, depressed, or hopeless',
      'Trouble falling or staying asleep, or sleeping too much',
      'Feeling tired or having little energy',
      'Poor appetite or overeating',
      'Feeling bad about yourself — or that you are a failure or have let yourself or your family down',
      'Trouble concentrating on things, such as reading or watching television',
      'Moving or speaking so slowly that other people could notice — or being so fidgety or restless that you have been moving around more than usual',
      'Thoughts that you would be better off dead, or of hurting yourself in some way',
    ],
    scale: [
      { value: 0, label: 'Not at all' },
      { value: 1, label: 'Several days' },
      { value: 2, label: 'More than half the days' },
      { value: 3, label: 'Nearly every day' },
    ],
    severity: [
      { max: 4, label: 'Minimal', blurb: 'Symptoms are minimal. Keep checking in.' },
      { max: 9, label: 'Mild', blurb: 'Mild symptoms — worth mentioning at your next visit.' },
      { max: 14, label: 'Moderate', blurb: 'Moderate symptoms — share with your healthcare provider.' },
      { max: 19, label: 'Moderately severe', blurb: 'Symptoms are moderately severe — please share with your provider.' },
      { max: 27, label: 'Severe', blurb: 'Severe symptoms — please contact your provider.' },
    ],
  },
  GAD7: {
    key: 'GAD7',
    title: 'Anxiety (GAD-7)',
    shortTitle: 'GAD-7',
    intro: 'Over the last 2 weeks, how often have you been bothered by the following?',
    questions: [
      'Feeling nervous, anxious, or on edge',
      'Not being able to stop or control worrying',
      'Worrying too much about different things',
      'Trouble relaxing',
      'Being so restless that it is hard to sit still',
      'Becoming easily annoyed or irritable',
      'Feeling afraid, as if something awful might happen',
    ],
    scale: [
      { value: 0, label: 'Not at all' },
      { value: 1, label: 'Several days' },
      { value: 2, label: 'More than half the days' },
      { value: 3, label: 'Nearly every day' },
    ],
    severity: [
      { max: 4, label: 'Minimal', blurb: 'Minimal anxiety symptoms.' },
      { max: 9, label: 'Mild', blurb: 'Mild anxiety — mention at your next visit.' },
      { max: 14, label: 'Moderate', blurb: 'Moderate anxiety — share with your provider.' },
      { max: 21, label: 'Severe', blurb: 'Severe anxiety — please contact your provider.' },
    ],
  },
  PSS10: {
    key: 'PSS10',
    title: 'Stress (PSS-10)',
    shortTitle: 'PSS-10',
    intro: 'In the last month, how often have you felt the following?',
    questions: [
      'Been upset because of something that happened unexpectedly?',
      'Felt that you were unable to control the important things in your life?',
      'Felt nervous and stressed?',
      'Felt confident about your ability to handle your personal problems?',
      'Felt that things were going your way?',
      'Found that you could not cope with all the things that you had to do?',
      'Been able to control irritations in your life?',
      'Felt that you were on top of things?',
      'Been angered because of things that were outside of your control?',
      'Felt difficulties were piling up so high that you could not overcome them?',
    ],
    scale: [
      { value: 0, label: 'Never' },
      { value: 1, label: 'Almost never' },
      { value: 2, label: 'Sometimes' },
      { value: 3, label: 'Fairly often' },
      { value: 4, label: 'Very often' },
    ],
    reverseScored: [3, 4, 6, 7],
    severity: [
      { max: 13, label: 'Low perceived stress', blurb: 'Stress is in the low range.' },
      { max: 26, label: 'Moderate perceived stress', blurb: 'Stress is in the moderate range — share with your provider.' },
      { max: 40, label: 'High perceived stress', blurb: 'Stress is in the high range — please share with your provider.' },
    ],
  },
  ISI: {
    key: 'ISI',
    title: 'Sleep (ISI)',
    shortTitle: 'ISI',
    intro: 'Please rate the current severity of your sleep difficulties.',
    questions: [
      'Difficulty falling asleep',
      'Difficulty staying asleep',
      'Problems waking up too early',
      'How satisfied/dissatisfied are you with your current sleep pattern?',
      'How noticeable to others do you think your sleep problem is?',
      'How worried/distressed are you about your current sleep problem?',
      'To what extent do you consider your sleep problem to interfere with your daily functioning?',
    ],
    scale: [
      { value: 0, label: 'None / Very satisfied' },
      { value: 1, label: 'Mild / Satisfied' },
      { value: 2, label: 'Moderate / Neutral' },
      { value: 3, label: 'Severe / Dissatisfied' },
      { value: 4, label: 'Very severe / Very dissatisfied' },
    ],
    severity: [
      { max: 7, label: 'No clinically significant insomnia', blurb: 'Sleep is in the healthy range.' },
      { max: 14, label: 'Subthreshold insomnia', blurb: 'Some sleep difficulty — share with your provider.' },
      { max: 21, label: 'Moderate insomnia', blurb: 'Moderate insomnia — please share with your provider.' },
      { max: 28, label: 'Severe insomnia', blurb: 'Severe insomnia — please contact your provider.' },
    ],
  },
  SYMPTOM: {
    key: 'SYMPTOM',
    title: 'Symptom check-in',
    shortTitle: 'Symptoms',
    intro: 'In the last 7 days, rate the severity of each symptom at its worst.',
    questions: [
      'Nausea',
      'Fatigue or tiredness',
      'Diarrhea',
      'Numbness or tingling in hands/feet (neuropathy)',
      'Pain',
      'Loss of appetite',
      'Mouth sores',
      'Hand-foot syndrome (redness, swelling, or peeling on palms/soles)',
      'Constipation',
      'Skin rash or dryness',
    ],
    scale: [
      { value: 0, label: 'None' },
      { value: 1, label: 'Mild' },
      { value: 2, label: 'Moderate' },
      { value: 3, label: 'Severe' },
      { value: 4, label: 'Very severe' },
    ],
    severity: [
      { max: 8, label: 'Mild symptoms', blurb: 'Symptom burden is in the mild range.' },
      { max: 18, label: 'Moderate symptoms', blurb: 'Moderate symptoms — share with your provider.' },
      { max: 28, label: 'Significant symptoms', blurb: 'Significant symptoms — please share with your provider.' },
      { max: 40, label: 'Severe symptoms', blurb: 'Severe symptoms — please contact your provider promptly.' },
    ],
  },
  PREMM5: {
    key: 'PREMM5',
    title: 'Lynch syndrome risk (PREMM5)',
    shortTitle: 'PREMM5',
    intro:
      'These questions help estimate hereditary cancer risk. About 10% of colorectal cancers have a hereditary component; this brief check-in helps identify if genetic counseling could benefit you and your family.',
    questions: [
      'Were you diagnosed with colorectal cancer before age 50?',
      'Were you diagnosed with endometrial (uterine) cancer at any age?',
      'Have you had more than one cancer diagnosis (any type)?',
      'Has a first-degree relative (parent, sibling, child) been diagnosed with colorectal cancer?',
      'Has a first-degree relative been diagnosed with endometrial, ovarian, stomach, urinary tract, or brain cancer?',
      'Have two or more relatives on the same side of the family had colorectal cancer?',
      'Have two or more relatives on the same side had endometrial, ovarian, stomach, urinary tract, or brain cancer?',
      'Was any relative diagnosed with colorectal cancer before age 50?',
      'Has anyone in your family been diagnosed with Lynch syndrome or a mismatch-repair gene mutation?',
      'Was your tumor tested for microsatellite instability (MSI) or mismatch repair (MMR) and shown MSI-High or dMMR?',
    ],
    scale: [
      { value: 0, label: 'No' },
      { value: 1, label: 'Yes' },
    ],
    severity: [
      { max: 1, label: 'Low risk', blurb: 'Lower hereditary cancer risk. Share with your provider.' },
      { max: 3, label: 'Moderate risk', blurb: 'Moderate hereditary risk — consider discussing genetic counseling with your provider. Find a counselor at nsgc.org.' },
      { max: 10, label: 'High risk', blurb: 'Elevated hereditary cancer risk — genetic counseling is recommended. Find a counselor at nsgc.org.' },
    ],
  },
};

function severityFor(def: InstrumentDef, total: number): SeverityBand {
  for (const band of def.severity) {
    if (total <= band.max) return band;
  }
  return def.severity[def.severity.length - 1];
}

function computeTotal(def: InstrumentDef, answers: (number | null)[]): number {
  const scaleMax = def.scale[def.scale.length - 1].value;
  return answers.reduce<number>((acc, a, i) => {
    if (a == null) return acc;
    const val = def.reverseScored?.includes(i) ? scaleMax - a : a;
    return acc + val;
  }, 0);
}

function isValidInstrument(k: string | undefined): k is ScreeningInstrument {
  return (
    k === 'PHQ9' ||
    k === 'GAD7' ||
    k === 'PSS10' ||
    k === 'ISI' ||
    k === 'SYMPTOM' ||
    k === 'PREMM5'
  );
}

export default function ScreeningScreen() {
  const params = useLocalSearchParams<{ instrument?: string }>();
  const initial = isValidInstrument(params.instrument) ? params.instrument : null;
  const [picked, setPicked] = useState<ScreeningInstrument | null>(initial);

  if (!picked) {
    return <InstrumentPicker onPick={setPicked} />;
  }
  return <InstrumentRunner def={INSTRUMENTS[picked]} onPickAnother={() => setPicked(null)} />;
}

function InstrumentPicker({ onPick }: { onPick: (i: ScreeningInstrument) => void }) {
  const items: { key: ScreeningInstrument; blurb: string }[] = [
    { key: 'SYMPTOM', blurb: 'How you’ve felt physically the last 7 days' },
    { key: 'PHQ9', blurb: 'How your mood has been over 2 weeks' },
    { key: 'GAD7', blurb: 'How anxious you’ve felt over 2 weeks' },
    { key: 'PSS10', blurb: 'How stressed you’ve felt this month' },
    { key: 'ISI', blurb: 'How well you’ve been sleeping' },
    { key: 'PREMM5', blurb: 'Hereditary cancer risk (Lynch syndrome)' },
  ];
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Wellness check-in', headerBackTitle: 'Tools' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 12 }}>
        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
          Quick, standardized check-ins. Results save to your Care snapshot.
        </Text>
        {items.map((it) => {
          const def = INSTRUMENTS[it.key];
          return (
            <Pressable
              key={it.key}
              onPress={() => onPick(it.key)}
              accessibilityRole="button"
              accessibilityLabel={`Start ${def.title}`}
              style={({ pressed }) => ({
                padding: 16,
                borderRadius: Radius.lg,
                borderWidth: 1,
                borderColor: pressed ? Colors.primary : Colors.border,
                backgroundColor: pressed ? Colors.primarySoft : Colors.surfaceMuted,
              })}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text
                    style={{
                      fontFamily: Fonts.sansSemiBold,
                      fontSize: 16,
                      color: Colors.textPrimary,
                    }}>
                    {def.title}
                  </Text>
                  <Text style={{ color: Colors.textMuted, fontSize: 13, marginTop: 4 }}>
                    {it.blurb} · {def.questions.length} questions
                  </Text>
                </View>
                <ChevronRight size={18} color={Colors.primary} />
              </View>
            </Pressable>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

function InstrumentRunner({
  def,
  onPickAnother,
}: {
  def: InstrumentDef;
  onPickAnother: () => void;
}) {
  const [answers, setAnswers] = useState<(number | null)[]>(
    Array(def.questions.length).fill(null),
  );
  // index === questions.length means we're on the result step
  const [index, setIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [resultScore, setResultScore] = useState<number | null>(null);
  const [crisis, setCrisis] = useState<ScreeningCrisisResources | null>(null);
  const [savedError, setSavedError] = useState<string | null>(null);
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ y: 0, animated: false });
    return () => {
      if (advanceTimer.current) clearTimeout(advanceTimer.current);
    };
  }, [index]);

  const onResult = index === def.questions.length;
  const total = useMemo(() => computeTotal(def, answers), [def, answers]);

  const pickAnswer = (value: number) => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    const next = [...answers];
    next[index] = value;
    setAnswers(next);
    advanceTimer.current = setTimeout(() => {
      setIndex((i) => Math.min(i + 1, def.questions.length));
    }, 280);
  };

  const goBack = () => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    if (index > 0) setIndex(index - 1);
  };

  const submit = async () => {
    setSubmitting(true);
    setSavedError(null);
    try {
      const scores: Record<string, number> = {};
      answers.forEach((a, i) => {
        scores[`q${i + 1}`] = a ?? 0;
      });
      const band = severityFor(def, total);
      const res = await saveScreening({
        instrument: def.key,
        scores,
        total_score: total,
        severity_label: band.label,
      });
      setResultScore(res.total_score);
      if (res.is_crisis && res.crisis_resources) setCrisis(res.crisis_resources);
    } catch {
      setSavedError('Could not save. Check your connection and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen
        options={{
          title: onResult ? def.shortTitle : `${def.shortTitle} · ${index + 1}/${def.questions.length}`,
          headerBackTitle: 'Wellness',
        }}
      />
      <View style={{ paddingHorizontal: 20, paddingTop: 12, gap: 8 }}>
        <ProgressBar
          fraction={onResult ? 1 : (index + 1) / def.questions.length}
        />
      </View>
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: 20, gap: 18, paddingBottom: 40 }}>
        {onResult ? (
          <ResultPanel
            def={def}
            answers={answers}
            total={total}
            resultScore={resultScore}
            submitting={submitting}
            savedError={savedError}
            onSubmit={submit}
            onRestart={() => {
              setAnswers(Array(def.questions.length).fill(null));
              setResultScore(null);
              setIndex(0);
            }}
            onPickAnother={onPickAnother}
          />
        ) : (
          <QuestionPanel
            def={def}
            index={index}
            selected={answers[index]}
            onPick={pickAnswer}
            onBack={index > 0 ? goBack : undefined}
          />
        )}
      </ScrollView>
      <CrisisModal resources={crisis} onClose={() => setCrisis(null)} />
    </SafeAreaView>
  );
}

function QuestionPanel({
  def,
  index,
  selected,
  onPick,
  onBack,
}: {
  def: InstrumentDef;
  index: number;
  selected: number | null;
  onPick: (v: number) => void;
  onBack?: () => void;
}) {
  return (
    <View style={{ gap: 18 }}>
      <View style={{ gap: 6 }}>
        {index === 0 && (
          <Text style={{ color: Colors.textMuted, fontSize: 13, lineHeight: 19 }}>{def.intro}</Text>
        )}
        <Text style={{ color: Colors.textMuted, fontSize: 12, fontFamily: Fonts.sansMedium }}>
          QUESTION {index + 1} OF {def.questions.length}
        </Text>
        <Text
          style={{
            fontFamily: Fonts.serifBold,
            fontSize: 22,
            color: Colors.textPrimary,
            lineHeight: 28,
          }}>
          {def.questions[index]}
        </Text>
      </View>
      <View style={{ gap: 10 }}>
        {def.scale.map((opt) => {
          const isSel = selected === opt.value;
          return (
            <Pressable
              key={opt.value}
              onPress={() => onPick(opt.value)}
              accessibilityRole="radio"
              accessibilityState={{ selected: isSel }}
              style={({ pressed }) => ({
                paddingHorizontal: 16,
                paddingVertical: 16,
                borderRadius: Radius.md,
                borderWidth: isSel ? 2 : 1,
                borderColor: isSel ? Colors.primary : Colors.border,
                backgroundColor: isSel
                  ? Colors.primarySoft
                  : pressed
                    ? Colors.sidebarBg
                    : Colors.surfaceMuted,
              })}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Text
                  style={{
                    flex: 1,
                    color: isSel ? Colors.primary : Colors.textPrimary,
                    fontFamily: isSel ? Fonts.sansSemiBold : Fonts.sansMedium,
                    fontSize: 15,
                  }}>
                  {opt.label}
                </Text>
                {isSel && <Check size={18} color={Colors.primary} style={{ marginLeft: 10 }} />}
              </View>
            </Pressable>
          );
        })}
      </View>
      {onBack && (
        <Pressable
          onPress={onBack}
          accessibilityRole="button"
          accessibilityLabel="Previous question"
          hitSlop={8}
          style={({ pressed }) => ({
            alignSelf: 'flex-start',
            flexDirection: 'row',
            alignItems: 'center',
            gap: 4,
            paddingVertical: 10,
            paddingHorizontal: 12,
            borderRadius: Radius.md,
            backgroundColor: pressed ? Colors.surfaceMuted : 'transparent',
          })}>
          <ChevronLeft size={16} color={Colors.primary} />
          <Text style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
            Back
          </Text>
        </Pressable>
      )}
    </View>
  );
}

function ResultPanel({
  def,
  answers,
  total,
  resultScore,
  submitting,
  savedError,
  onSubmit,
  onRestart,
  onPickAnother,
}: {
  def: InstrumentDef;
  answers: (number | null)[];
  total: number;
  resultScore: number | null;
  submitting: boolean;
  savedError: string | null;
  onSubmit: () => void;
  onRestart: () => void;
  onPickAnother: () => void;
}) {
  const allAnswered = answers.every((a) => a !== null);
  if (!allAnswered) {
    return (
      <View style={{ gap: 12 }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 20, color: Colors.textPrimary }}>
          A few unanswered
        </Text>
        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>
          Tap Back to fill in the remaining questions, then save.
        </Text>
        <Button label="Go back to questions" variant="secondary" fullWidth onPress={onRestart} />
      </View>
    );
  }
  const band = severityFor(def, total);
  const saved = resultScore !== null;
  return (
    <View style={{ gap: 16 }}>
      <Text style={{ fontFamily: Fonts.serifBold, fontSize: 24, color: Colors.textPrimary }}>
        {saved ? 'Saved' : 'Your result'}
      </Text>
      <View
        style={{
          borderRadius: Radius.lg,
          backgroundColor: Colors.sidebarBg,
          padding: 16,
          gap: 8,
        }}>
        <Text style={{ color: Colors.textMuted, fontSize: 12, fontFamily: Fonts.sansMedium }}>
          {def.shortTitle} SCORE
        </Text>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 36, color: Colors.textPrimary }}>
          {total}
        </Text>
        <Text
          style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: 16 }}>
          {band.label}
        </Text>
        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
          {band.blurb}
        </Text>
      </View>
      {savedError && (
        <Text style={{ color: Colors.danger, fontSize: 13 }}>{savedError}</Text>
      )}
      {!saved ? (
        <Button
          label="Save to my Care snapshot"
          size="lg"
          fullWidth
          loading={submitting}
          onPress={onSubmit}
        />
      ) : (
        <Button label="Take another check-in" variant="secondary" fullWidth onPress={onPickAnother} />
      )}
      <Button
        label="Back to chat"
        variant="ghost"
        fullWidth
        onPress={() => router.replace('/(tabs)')}
      />
    </View>
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

function CrisisModal({
  resources,
  onClose,
}: {
  resources: ScreeningCrisisResources | null;
  onClose: () => void;
}) {
  if (!resources) return null;
  return (
    <Modal visible animationType="fade" transparent onRequestClose={onClose}>
      <View
        style={{
          flex: 1,
          backgroundColor: 'rgba(15,32,28,0.55)',
          justifyContent: 'center',
          padding: 20,
        }}>
        <View
          style={{
            backgroundColor: Colors.surface,
            borderRadius: Radius.lg,
            padding: 20,
            gap: 12,
          }}>
          <Text
            style={{ fontFamily: Fonts.serifBold, fontSize: 19, color: Colors.textPrimary }}>
            We're here for you
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
            {resources.message}
          </Text>
          <View style={{ gap: 8 }}>
            {resources.resources.map((r) => {
              const phoneMatch = r.contact.match(/(\d{3}[- ]?\d{3}[- ]?\d{4}|988|911)/);
              const phone = phoneMatch ? phoneMatch[0].replace(/[^0-9]/g, '') : null;
              return (
                <Pressable
                  key={r.name}
                  onPress={() => phone && Linking.openURL(`tel:${phone}`).catch(() => {})}
                  accessibilityRole={phone ? 'button' : undefined}
                  style={({ pressed }) => ({
                    flexDirection: 'row',
                    gap: 10,
                    alignItems: 'center',
                    padding: 12,
                    borderRadius: Radius.md,
                    backgroundColor: pressed ? Colors.sidebarBg : Colors.surfaceMuted,
                  })}>
                  {phone && <Phone size={16} color={Colors.primary} />}
                  <View style={{ flex: 1 }}>
                    <Text
                      style={{
                        color: Colors.textPrimary,
                        fontFamily: Fonts.sansSemiBold,
                        fontSize: 13,
                      }}>
                      {r.name}
                    </Text>
                    <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>{r.contact}</Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
          <Button label="Close" variant="secondary" fullWidth onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

