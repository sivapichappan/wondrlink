/**
 * Publication screen (SPEC §5.7). Admin only.
 *
 * The database decides; this screen only shows the decision. It lists every
 * blocker at once rather than the first, because that list IS the work: each
 * line is one thing to fix before a version can reach patients. Publish stays
 * disabled while any blocker remains — and the server would refuse anyway,
 * since there is no override anywhere in this feature.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { AlertCircle, CheckCircle2 } from 'lucide-react-native';
import { ActivityIndicator, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Screen } from '@/components/ui/Screen';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { fetchVersionBlockers, publishVersion } from '@/lib/api/review';

export default function PublishScreen() {
  const { versionId } = useLocalSearchParams<{ versionId: string }>();
  const qc = useQueryClient();

  const blockers = useQuery({
    queryKey: ['review-blockers', versionId],
    queryFn: () => fetchVersionBlockers(String(versionId)),
    enabled: !!versionId,
  });

  const publish = useMutation({
    mutationFn: () => publishVersion(String(versionId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review-blockers', versionId] });
      qc.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });

  const list = blockers.data?.blockers ?? [];
  const publishable = blockers.data?.publishable === true;

  return (
    <Screen gap={Spacing.lg}>
      <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
        Publishing makes every connection in this version eligible to reach patients.
        It cannot be undone or edited afterwards; a correction means a new version.
      </Text>

      {blockers.isLoading ? (
        <View style={{ paddingVertical: Spacing.xxl, alignItems: 'center' }}>
          <ActivityIndicator color={Colors.primary} />
        </View>
      ) : null}

      {blockers.isError ? (
        <Card>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.textPrimary }}>
            Could not check this version. Nothing was published.
          </Text>
        </Card>
      ) : null}

      {blockers.data && publishable ? (
        <Card gap={Spacing.md}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
            <CheckCircle2 size={18} color={Colors.success} />
            <Text style={{ fontFamily: Fonts.sansBold, fontSize: FontSize.md, color: Colors.textPrimary }}>
              Every check passed
            </Text>
          </View>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
            Each connection is approved, signed by a physician, and its quotations still
            match their sources word for word.
          </Text>
          <Button
            label="Publish this version"
            onPress={() => publish.mutate()}
            loading={publish.isPending}
            disabled={publish.isSuccess}
          />
        </Card>
      ) : null}

      {blockers.data && !publishable ? (
        <View style={{ gap: Spacing.sm }}>
          <SectionLabel>
            {`${list.length} thing${list.length === 1 ? '' : 's'} to fix first`}
          </SectionLabel>
          {list.map((b, i) => (
            <View
              key={`${b.edge_id ?? 'version'}-${i}`}
              style={{
                flexDirection: 'row',
                gap: Spacing.sm,
                backgroundColor: Colors.warningBg,
                borderRadius: Radius.md,
                padding: Spacing.md,
              }}>
              <AlertCircle size={16} color={Colors.warning} />
              <Text style={{ flex: 1, fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.warning }}>
                {b.problem}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      {publish.isSuccess ? (
        <Card>
          <Text style={{ fontFamily: Fonts.sansBold, fontSize: FontSize.md, color: Colors.textPrimary }}>
            Published.
          </Text>
        </Card>
      ) : null}

      {publish.isError ? (
        <Card>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.danger }}>
            Publishing was refused and nothing changed. Reload to see what is outstanding.
          </Text>
        </Card>
      ) : null}
    </Screen>
  );
}
