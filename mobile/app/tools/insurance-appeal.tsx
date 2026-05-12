import { Stack, router } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import { FileText, X } from 'lucide-react-native';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MarkdownText } from '@/components/chat/MarkdownText';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { submitInsuranceAppeal } from '@/lib/api/tools';
import type { InsuranceAppealResponse } from '@shared/types';

interface PickedPdf {
  uri: string;
  name: string;
  mimeType?: string;
}

export default function InsuranceAppealScreen() {
  const [denialText, setDenialText] = useState('');
  const [pdf, setPdf] = useState<PickedPdf | null>(null);
  const [result, setResult] = useState<InsuranceAppealResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pickPdf = async () => {
    try {
      const res = await DocumentPicker.getDocumentAsync({ type: 'application/pdf', copyToCacheDirectory: true });
      if (res.canceled) return;
      const file = res.assets?.[0];
      if (file) setPdf({ uri: file.uri, name: file.name, mimeType: file.mimeType ?? 'application/pdf' });
    } catch {
      setError('Could not open the file picker.');
    }
  };

  const submit = async () => {
    setError(null);
    if (!pdf && denialText.trim().length < 50) {
      setError('Either describe the denial in at least 50 characters or attach a PDF.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await submitInsuranceAppeal({
        denialText: denialText.trim() || undefined,
        pdf: pdf || undefined,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.body?.error ?? 'Could not draft a letter.' : 'Could not draft a letter.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Insurance appeal', headerBackTitle: 'Tools' }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            Paste the denial reason or attach the denial letter PDF. WondrChat will draft an
            appeal grounded in NCCN/ASCO guidelines for your situation.
          </Text>

          <TextField
            label="Denial reason"
            multiline
            placeholder="What did the insurer say? Why was it denied?"
            value={denialText}
            onChangeText={setDenialText}
            style={{ minHeight: 120, paddingTop: 12, textAlignVertical: 'top' }}
          />

          {pdf ? (
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 10,
                padding: 12,
                borderRadius: Radius.md,
                backgroundColor: Colors.sidebarBg,
              }}>
              <FileText size={18} color={Colors.primary} />
              <Text
                style={{
                  flex: 1,
                  color: Colors.textPrimary,
                  fontSize: 13,
                  fontFamily: Fonts.sansMedium,
                }}
                numberOfLines={1}>
                {pdf.name}
              </Text>
              <Pressable onPress={() => setPdf(null)} hitSlop={8} accessibilityLabel="Remove PDF">
                <X size={18} color={Colors.textMuted} />
              </Pressable>
            </View>
          ) : (
            <Button
              label="Attach denial letter PDF (optional)"
              variant="secondary"
              fullWidth
              leadingIcon={<FileText size={16} color={Colors.primary} />}
              onPress={pickPdf}
            />
          )}

          {error && <Text style={{ color: Colors.danger, fontSize: 13 }}>{error}</Text>}

          <Button
            label={submitting ? 'Drafting…' : 'Draft appeal letter'}
            fullWidth
            size="lg"
            loading={submitting}
            onPress={submit}
          />

          {result && result.status === 'ok' && (
            <View
              style={{
                padding: 14,
                borderRadius: Radius.lg,
                borderWidth: 1,
                borderColor: Colors.border,
                backgroundColor: Colors.surface,
              }}>
              <Text
                style={{
                  fontFamily: Fonts.sansSemiBold,
                  fontSize: 13,
                  color: Colors.primary,
                  letterSpacing: 0.3,
                  marginBottom: 8,
                }}>
                DRAFT APPEAL
              </Text>
              <MarkdownText>{result.draft}</MarkdownText>
              {result.sources?.length > 0 && (
                <View style={{ marginTop: 12, gap: 6 }}>
                  <Text
                    style={{
                      color: Colors.textMuted,
                      fontSize: 11,
                      fontFamily: Fonts.sansMedium,
                      letterSpacing: 0.4,
                    }}>
                    GUIDELINE SOURCES
                  </Text>
                  {result.sources.map((s, i) => (
                    <Text
                      key={`${s.title}-${i}`}
                      style={{
                        color: Colors.textSecondary,
                        fontSize: 12,
                        lineHeight: 18,
                      }}>
                      • {s.title}
                    </Text>
                  ))}
                </View>
              )}
            </View>
          )}

          <Button label="Back to tools" variant="ghost" fullWidth onPress={() => router.back()} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
