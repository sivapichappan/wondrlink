/**
 * My terms — the personal term dictionary ("Ask about a term or phrase").
 *
 * TOP: type a term -> AI returns a SHORT plain-words explanation -> the
 * definition is editable -> save to the library.
 * BELOW: every saved term as an expandable card (view / edit / delete).
 *
 * NativeWind rule: Pressable visuals live on static inner Views; style
 * functions are opacity-only.
 */

import { Stack } from 'expo-router';
import { BookOpen, ChevronDown, ChevronUp, Pencil, Trash2 } from 'lucide-react-native';
import { useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { IconCircle } from '@/components/ui/IconCircle';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { useGlossary } from '@/hooks/useGlossary';
import { explainTerm } from '@/lib/api/tools';
import { ApiError } from '@/lib/api/client';
import type { GlossaryTerm } from '@shared/types';

export default function GlossaryScreen() {
  const { terms, isLoading, addTerm, adding, updateTerm, removeTerm } = useGlossary();

  // --- add-new-term composer state ---
  const [term, setTerm] = useState('');
  const [definition, setDefinition] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const explain = async () => {
    const t = term.trim();
    if (!t) return;
    setExplaining(true);
    setError(null);
    try {
      const res = await explainTerm(t);
      setDefinition(res.definition);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? ((e.body as { error?: string })?.error ?? 'Could not explain that right now.')
          : 'Could not explain that right now.',
      );
    } finally {
      setExplaining(false);
    }
  };

  const save = async () => {
    const t = term.trim();
    const d = (definition ?? '').trim();
    if (!t || !d) return;
    setError(null);
    try {
      await addTerm({ term: t, definition: d });
      setTerm('');
      setDefinition(null);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? ((e.body as { error?: string })?.error ?? 'Could not save that term.')
          : 'Could not save that term.',
      );
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'My terms', headerBackTitle: 'Tools' }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={{ padding: Spacing.xl, gap: Spacing.lg }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          <Text style={{ color: Colors.textSecondary, fontSize: FontSize.sm, lineHeight: 19 }}>
            Heard a word you did not understand? Type it below and get a plain-words
            explanation you can keep.
          </Text>

          {/* ---- Add a new term ---- */}
          <TextField
            label="Term or phrase"
            value={term}
            onChangeText={(v) => {
              setTerm(v);
              if (definition !== null) setDefinition(null);
            }}
            placeholder="e.g. neoadjuvant, ctDNA, margins"
            maxLength={120}
            autoCapitalize="none"
            returnKeyType="search"
            onSubmitEditing={explain}
          />
          {definition === null ? (
            <Button
              label={explaining ? 'Thinking…' : 'Explain it'}
              loading={explaining}
              disabled={!term.trim() || explaining}
              onPress={explain}
              fullWidth
            />
          ) : (
            <View style={{ gap: Spacing.sm }}>
              <TextField
                label="Plain-words definition"
                value={definition}
                onChangeText={setDefinition}
                multiline
                hint="You can edit this before saving."
                style={{ minHeight: 120, paddingTop: 12, textAlignVertical: 'top' }}
              />
              <Button
                label={adding ? 'Saving…' : 'Save to my terms'}
                loading={adding}
                disabled={!definition.trim() || adding}
                onPress={save}
                fullWidth
              />
              <Button
                label="Try a different explanation"
                variant="ghost"
                disabled={explaining}
                onPress={explain}
                fullWidth
              />
            </View>
          )}
          {error && (
            <Text style={{ color: Colors.danger, fontSize: FontSize.sm }}>{error}</Text>
          )}

          {/* ---- Saved terms ---- */}
          <SectionLabel>Your terms</SectionLabel>
          {terms.length === 0 && !isLoading ? (
            <View
              style={{
                alignItems: 'center',
                gap: Spacing.sm,
                paddingVertical: Spacing.xl,
              }}>
              <IconCircle size={44} bg={Colors.primarySoft}>
                <BookOpen size={20} color={Colors.primaryPressed} />
              </IconCircle>
              <Text
                style={{
                  color: Colors.textMuted,
                  fontSize: FontSize.sm,
                  textAlign: 'center',
                  lineHeight: 19,
                }}>
                Terms you save will appear here.{'\n'}Try adding one above.
              </Text>
            </View>
          ) : (
            <View style={{ gap: Spacing.sm }}>
              {terms.map((t) => (
                <TermCard
                  key={t.id}
                  item={t}
                  onSaveEdit={(patch) => updateTerm({ id: t.id, patch })}
                  onDelete={() => {
                    Alert.alert('Delete this term?', `"${t.term}" will be removed from your library.`, [
                      { text: 'Cancel', style: 'cancel' },
                      { text: 'Delete', style: 'destructive', onPress: () => removeTerm(t.id) },
                    ]);
                  }}
                />
              ))}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function TermCard({
  item,
  onSaveEdit,
  onDelete,
}: {
  item: GlossaryTerm;
  onSaveEdit: (patch: { definition: string }) => Promise<unknown>;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.definition);
  const [busy, setBusy] = useState(false);

  const saveEdit = async () => {
    const d = draft.trim();
    if (!d) return;
    setBusy(true);
    try {
      await onSaveEdit({ definition: d });
      setEditing(false);
    } catch {
      // keep editing open; the list refetch will reconcile on success elsewhere
    } finally {
      setBusy(false);
    }
  };

  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        backgroundColor: Colors.surfaceMuted,
      }}>
      <Pressable
        onPress={() => {
          setExpanded((v) => !v);
          if (expanded) setEditing(false);
        }}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        accessibilityLabel={item.term}
        style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: Spacing.sm,
            padding: Spacing.md,
          }}>
          <Text
            style={{
              flex: 1,
              fontFamily: Fonts.sansSemiBold,
              fontSize: FontSize.md,
              color: Colors.textPrimary,
            }}>
            {item.term}
          </Text>
          {expanded ? (
            <ChevronUp size={16} color={Colors.textMuted} />
          ) : (
            <ChevronDown size={16} color={Colors.textMuted} />
          )}
        </View>
      </Pressable>

      {expanded && (
        <View style={{ paddingHorizontal: Spacing.md, paddingBottom: Spacing.md, gap: Spacing.sm }}>
          {editing ? (
            <>
              <TextField
                value={draft}
                onChangeText={setDraft}
                multiline
                style={{ minHeight: 100, paddingTop: 12, textAlignVertical: 'top' }}
              />
              <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
                <Button
                  label={busy ? 'Saving…' : 'Save'}
                  size="sm"
                  loading={busy}
                  disabled={!draft.trim() || busy}
                  onPress={saveEdit}
                />
                <Button
                  label="Cancel"
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onPress={() => {
                    setDraft(item.definition);
                    setEditing(false);
                  }}
                />
              </View>
            </>
          ) : (
            <>
              <Text style={{ fontSize: FontSize.sm, lineHeight: 20, color: Colors.textSecondary }}>
                {item.definition}
              </Text>
              <View style={{ flexDirection: 'row', gap: Spacing.lg }}>
                <Pressable
                  onPress={() => setEditing(true)}
                  accessibilityRole="button"
                  accessibilityLabel={`Edit ${item.term}`}
                  style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                    <Pencil size={13} color={Colors.primary} />
                    <Text style={{ fontSize: FontSize.sm, color: Colors.primary, fontFamily: Fonts.sansSemiBold }}>
                      Edit
                    </Text>
                  </View>
                </Pressable>
                <Pressable
                  onPress={onDelete}
                  accessibilityRole="button"
                  accessibilityLabel={`Delete ${item.term}`}
                  style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                    <Trash2 size={13} color={Colors.danger} />
                    <Text style={{ fontSize: FontSize.sm, color: Colors.danger, fontFamily: Fonts.sansSemiBold }}>
                      Delete
                    </Text>
                  </View>
                </Pressable>
              </View>
            </>
          )}
        </View>
      )}
    </View>
  );
}
