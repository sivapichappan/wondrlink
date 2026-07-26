/**
 * Scan a report — photograph/upload a medical report, confirm the facts.
 *
 * PRIVACY DESIGN (deviation #8, docs/sage-implementation-guidelines-notes.md):
 * photos are OCR'd ON THE PHONE (Google ML Kit) and NEVER uploaded; only the
 * OCR text goes to the backend, which de-identifies + PII-gates it before any
 * AI call. Image URIs are discarded as soon as OCR finishes. PDFs with a text
 * layer upload via multipart and are extracted-then-discarded server-side.
 *
 * Nothing writes to the profile until the patient confirms each fact on the
 * REVIEW step ("Save N confirmed" -> /api/report/apply).
 *
 * NativeWind rule: Pressable visuals live on static inner Views; style
 * functions are opacity-only.
 */

import { requireOptionalNativeModule } from 'expo';
import * as DocumentPicker from 'expo-document-picker';
import type * as ImagePickerTypes from 'expo-image-picker';
import type * as MlkitOcrTypes from 'expo-mlkit-ocr';
import { Stack, router } from 'expo-router';
import { Camera, Check, FileText, Images, ShieldCheck, X } from 'lucide-react-native';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { IconCircle } from '@/components/ui/IconCircle';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { applyReportFacts, extractReportPdf, extractReportText } from '@/lib/api/tools';
import type { ReportExtractResponse, ReportFinding } from '@shared/types';

const MAX_PAGES = 3;
const MAX_CHARS = 8000;

const PHOTO_UNAVAILABLE_MSG =
  'Photo scanning is not in this version of the app yet. Attach a PDF or type the values instead.';

// expo-image-picker and expo-mlkit-ocr are native modules that a given install
// may not contain (their pods only link on builds with the iOS 16 deployment
// target). Their JS entry calls requireNativeModule at module scope, which
// throws when the binary lacks the pod — and Metro routes a module factory
// throw from an event handler to ErrorUtils.reportFatalError (app crash), so
// a try/catch around require() can NOT contain it. Probe the native registry
// with requireOptionalNativeModule FIRST; only require() the package once the
// probe proves its factory cannot throw.
function loadImagePicker(): typeof ImagePickerTypes | null {
  if (!requireOptionalNativeModule('ExponentImagePicker')) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('expo-image-picker');
  } catch {
    return null;
  }
}

function loadOcr(): typeof MlkitOcrTypes | null {
  if (!requireOptionalNativeModule('ExpoMlkitOcr')) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('expo-mlkit-ocr');
  } catch {
    return null;
  }
}

type Phase = 'capture' | 'processing' | 'review' | 'success';

export default function ReportScanScreen() {
  const [phase, setPhase] = useState<Phase>('capture');
  const [pageTexts, setPageTexts] = useState<string[]>([]);
  const [processingLabel, setProcessingLabel] = useState('');
  const [result, setResult] = useState<ReportExtractResponse | null>(null);
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [savedCount, setSavedCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typeInsteadHint, setTypeInsteadHint] = useState(false);

  const fail = (message: string, showTypeHint = false) => {
    setPhase('capture');
    setProcessingLabel('');
    setError(message);
    setTypeInsteadHint(showTypeHint);
  };

  const runExtraction = async (texts: string[]) => {
    const joined = texts.join('\n\n').slice(0, MAX_CHARS);
    setPhase('processing');
    setProcessingLabel('Pulling out the facts…');
    try {
      const res = await extractReportText(joined);
      if (!res.findings.length && !res.display_only.length) {
        fail('No medical facts found in that text. Try a clearer photo of the results section.');
        return;
      }
      setResult(res);
      setConfirmed({});
      setPhase('review');
      setError(null);
    } catch (e) {
      handleApiError(e);
    }
  };

  const handleApiError = (e: unknown) => {
    if (e instanceof ApiError) {
      const body = e.body as { error?: string; message?: string };
      if (body?.error === 'pii_guard') {
        fail(body.message ?? 'We could not safely read this report.', true);
        return;
      }
      if (body?.error === 'scanned_pdf') {
        fail(body.message ?? 'That PDF has no readable text. Photograph the pages instead.');
        return;
      }
      fail(body?.message ?? body?.error ?? 'Could not read that report right now.');
      return;
    }
    fail('Could not read that report right now.');
  };

  const ocrPage = async (ocr: typeof MlkitOcrTypes, uri: string) => {
    setPhase('processing');
    setProcessingLabel('Reading on your phone…');
    try {
      const recognized = await ocr.recognizeText(uri);
      const text = (recognized?.text ?? '').trim();
      // The image URI is dropped here; only text continues.
      if (text.length < 40) {
        fail('Could not read much text from that photo. Try again with better light, holding the phone flat.');
        return;
      }
      const nextTexts = [...pageTexts, text];
      setPageTexts(nextTexts);
      if (nextTexts.length >= MAX_PAGES) {
        await runExtraction(nextTexts);
      } else {
        setPhase('capture');
        setError(null);
      }
    } catch {
      fail('Could not read that photo on this device. You can type the values instead.', true);
    }
  };

  const takePhoto = async () => {
    const picker = loadImagePicker();
    const ocr = loadOcr();
    if (!picker || !ocr) {
      fail(PHOTO_UNAVAILABLE_MSG, true);
      return;
    }
    const perm = await picker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      fail('Camera access is off. You can allow it in Settings, pick from your photos, or type the values.', true);
      return;
    }
    const res = await picker.launchCameraAsync({ quality: 0.9 });
    if (!res.canceled && res.assets?.[0]?.uri) await ocrPage(ocr, res.assets[0].uri);
  };

  const pickPhoto = async () => {
    const picker = loadImagePicker();
    const ocr = loadOcr();
    if (!picker || !ocr) {
      fail(PHOTO_UNAVAILABLE_MSG, true);
      return;
    }
    const res = await picker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.9,
    });
    if (!res.canceled && res.assets?.[0]?.uri) await ocrPage(ocr, res.assets[0].uri);
  };

  const pickPdf = async () => {
    const res = await DocumentPicker.getDocumentAsync({
      type: 'application/pdf',
      copyToCacheDirectory: true,
    });
    if (res.canceled || !res.assets?.[0]) return;
    const asset = res.assets[0];
    setPhase('processing');
    setProcessingLabel('Reading the PDF…');
    try {
      const extracted = await extractReportPdf({
        uri: asset.uri,
        name: asset.name ?? 'report.pdf',
        mimeType: asset.mimeType ?? 'application/pdf',
      });
      if (!extracted.findings.length && !extracted.display_only.length) {
        fail('No medical facts found in that PDF.');
        return;
      }
      setResult(extracted);
      setConfirmed({});
      setPhase('review');
      setError(null);
    } catch (e) {
      handleApiError(e);
    }
  };

  const confirmedCount = Object.values(confirmed).filter(Boolean).length;

  const save = async () => {
    if (!result || confirmedCount === 0) return;
    setSaving(true);
    setError(null);
    try {
      const facts = result.findings
        .filter((f) => confirmed[f.path])
        .map((f) => ({ path: f.path, value: f.value }));
      const res = await applyReportFacts(facts);
      setSavedCount(res.applied);
      setPhase('success');
    } catch (e) {
      setError(
        e instanceof ApiError
          ? ((e.body as { error?: string })?.error ?? 'Could not save. Please try again.')
          : 'Could not save. Please try again.',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Scan a report', headerBackTitle: 'Tools' }} />
      <ScrollView
        contentContainerStyle={{ padding: Spacing.xl, gap: Spacing.lg }}
        showsVerticalScrollIndicator={false}>
        {phase === 'capture' && (
          <>
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.sm, lineHeight: 19 }}>
              Snap a photo of a pathology or test report and confirm what it says. No typing,
              no medical words needed.
            </Text>
            <View
              style={{
                flexDirection: 'row',
                gap: Spacing.sm,
                alignItems: 'flex-start',
                backgroundColor: Colors.primarySoft,
                borderRadius: Radius.md,
                padding: Spacing.md,
              }}>
              <ShieldCheck size={16} color={Colors.primaryPressed} style={{ marginTop: 1 }} />
              <Text style={{ flex: 1, fontSize: FontSize.sm, lineHeight: 19, color: Colors.primaryPressed }}>
                The photo is read on your phone and never uploaded. Only de-identified text is
                used.
              </Text>
            </View>

            {pageTexts.length > 0 && (
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: Spacing.sm,
                  backgroundColor: Colors.surfaceMuted,
                  borderRadius: Radius.md,
                  padding: Spacing.md,
                }}>
                <Check size={15} color={Colors.primary} />
                <Text style={{ flex: 1, fontSize: FontSize.sm, color: Colors.textSecondary }}>
                  {pageTexts.length} page{pageTexts.length > 1 ? 's' : ''} read. Add another page
                  or continue.
                </Text>
              </View>
            )}

            <CaptureChoice Icon={Camera} title="Take a photo" subtitle="Point at the report page" onPress={takePhoto} />
            <CaptureChoice Icon={Images} title="Choose from photos" subtitle="A photo you already took" onPress={pickPhoto} />
            <CaptureChoice Icon={FileText} title="Attach a PDF" subtitle="A report file from your patient portal" onPress={pickPdf} />

            {pageTexts.length > 0 && (
              <Button
                label="Continue with what I have"
                fullWidth
                onPress={() => runExtraction(pageTexts)}
              />
            )}

            {error && (
              <View style={{ gap: Spacing.xs }}>
                <Text style={{ color: Colors.danger, fontSize: FontSize.sm, lineHeight: 19 }}>{error}</Text>
                {typeInsteadHint && (
                  <Pressable
                    onPress={() => router.push('/profile/build' as never)}
                    accessibilityRole="button"
                    style={({ pressed }) => ({ opacity: pressed ? 0.8 : 1 })}>
                    <Text style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.sm }}>
                      Type the values instead →
                    </Text>
                  </Pressable>
                )}
              </View>
            )}
          </>
        )}

        {phase === 'processing' && (
          <View style={{ alignItems: 'center', gap: Spacing.md, paddingVertical: Spacing.xl * 2 }}>
            <ActivityIndicator color={Colors.primary} size="large" />
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.md }}>{processingLabel}</Text>
          </View>
        )}

        {phase === 'review' && result && (
          <>
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.sm, lineHeight: 19 }}>
              Here is what the report says. Confirm each item that looks right. Nothing is saved
              until you tap Save.
            </Text>
            <View style={{ gap: Spacing.sm }}>
              {result.findings.map((f) => (
                <FindingCard
                  key={f.path}
                  finding={f}
                  state={confirmed[f.path]}
                  onSet={(v) => setConfirmed((c) => ({ ...c, [f.path]: v }))}
                />
              ))}
            </View>
            {result.display_only.length > 0 && (
              <>
                <SectionLabel>For your reference — not saved</SectionLabel>
                <View
                  style={{
                    backgroundColor: Colors.surfaceMuted,
                    borderRadius: Radius.md,
                    padding: Spacing.md,
                    gap: 4,
                  }}>
                  {result.display_only.map((d, i) => (
                    <Text key={i} style={{ fontSize: FontSize.sm, color: Colors.textSecondary }}>
                      {d.label}: {d.value}
                    </Text>
                  ))}
                </View>
              </>
            )}
            <Button
              label={saving ? 'Saving…' : `Save ${confirmedCount} confirmed`}
              loading={saving}
              disabled={confirmedCount === 0 || saving}
              onPress={save}
              fullWidth
            />
            <Button
              label="Start over"
              variant="ghost"
              fullWidth
              onPress={() => {
                setPageTexts([]);
                setResult(null);
                setConfirmed({});
                setPhase('capture');
              }}
            />
            {error && <Text style={{ color: Colors.danger, fontSize: FontSize.sm }}>{error}</Text>}
          </>
        )}

        {phase === 'success' && (
          <View style={{ alignItems: 'center', gap: Spacing.md, paddingVertical: Spacing.xl * 2 }}>
            <IconCircle size={52} bg={Colors.primarySoft}>
              <Check size={26} color={Colors.primaryPressed} />
            </IconCircle>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.h3, color: Colors.textPrimary }}>
              {savedCount} fact{savedCount === 1 ? '' : 's'} saved
            </Text>
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.sm, textAlign: 'center', lineHeight: 19 }}>
              They are part of your profile now, so answers and trial matches can use them.
            </Text>
            <Button label="See my profile" onPress={() => router.push('/profile' as never)} />
            <Button label="Done" variant="ghost" onPress={() => router.back()} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function CaptureChoice({
  Icon,
  title,
  subtitle,
  onPress,
}: {
  Icon: typeof Camera;
  title: string;
  subtitle: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={title}
      style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: Spacing.md,
          borderWidth: 1.5,
          borderColor: Colors.border,
          borderRadius: Radius.lg,
          padding: Spacing.lg,
          backgroundColor: Colors.surface,
        }}>
        <IconCircle size={44} bg={Colors.primarySoft}>
          <Icon size={20} color={Colors.primaryPressed} />
        </IconCircle>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: FontSize.lg, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
            {title}
          </Text>
          <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 2 }}>{subtitle}</Text>
        </View>
      </View>
    </Pressable>
  );
}

function FindingCard({
  finding,
  state,
  onSet,
}: {
  finding: ReportFinding;
  state: boolean | undefined;
  onSet: (v: boolean) => void;
}) {
  const valueText =
    typeof finding.value === 'object' && finding.value !== null
      ? String((finding.value as { regimen?: string }).regimen ?? JSON.stringify(finding.value))
      : String(finding.value);
  return (
    <View
      style={{
        borderWidth: 1.5,
        borderColor: state === true ? Colors.primary : Colors.border,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        gap: Spacing.sm,
        backgroundColor: state === false ? Colors.surfaceMuted : Colors.surface,
        opacity: state === false ? 0.6 : 1,
      }}>
      <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted }}>{finding.label}</Text>
      <Text style={{ fontSize: FontSize.lg, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
        {valueText}
      </Text>
      {!!finding.evidence && (
        <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, fontStyle: 'italic' }}>
          Report says: “{finding.evidence}”
        </Text>
      )}
      <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
        <ToggleChip
          label="Looks right"
          Icon={Check}
          active={state === true}
          onPress={() => onSet(true)}
        />
        <ToggleChip
          label="Not right"
          Icon={X}
          active={state === false}
          onPress={() => onSet(false)}
        />
      </View>
    </View>
  );
}

function ToggleChip({
  label,
  Icon,
  active,
  onPress,
}: {
  label: string;
  Icon: typeof Check;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      accessibilityLabel={label}
      style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 6,
          paddingHorizontal: Spacing.md,
          paddingVertical: 8,
          borderRadius: Radius.pill,
          borderWidth: 1,
          borderColor: active ? Colors.primary : Colors.border,
          backgroundColor: active ? Colors.primarySoft : Colors.surface,
        }}>
        <Icon size={14} color={active ? Colors.primaryPressed : Colors.textMuted} />
        <Text
          style={{
            fontSize: FontSize.sm,
            fontFamily: Fonts.sansSemiBold,
            color: active ? Colors.primaryPressed : Colors.textSecondary,
          }}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}
