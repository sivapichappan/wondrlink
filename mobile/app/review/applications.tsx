/**
 * Reviewer applications — the admin dashboard (§5.2).
 *
 * Approving here is what turns "anyone may ask" into "no self-registration".
 * The credential fields are the whole point of the screen: an attestation
 * snapshots the signer's capacity, so the admin is verifying a specific person's
 * licence before that person's name goes on wording patients read.
 *
 * Approving is TWO deliberate taps and the second one names the person. It is
 * effectively irreversible: rejecting later sets 'revoked', which is a different
 * state from never-approved, and in between the account can sign. The same rule
 * the review queue learned the hard way (one tap on one of eight identical
 * buttons, over 82 rows, with a thumb).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BadgeCheck, Building2, Mail, MapPin } from 'lucide-react-native';
import { useState } from 'react';
import { ActivityIndicator, RefreshControl, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pill } from '@/components/ui/Pill';
import { Screen } from '@/components/ui/Screen';
import { Colors, FontSize, Fonts, Spacing } from '@/constants/theme';
import {
  decideApplication,
  fetchApplications,
  type PendingApplication,
} from '@/lib/api/review';

const APPLICATIONS_KEY = ['review', 'applications'] as const;

/** What a failed decision means, in words an admin can act on. */
function decisionError(err: unknown): string {
  const e = err as { status?: number; body?: { error?: string } };
  switch (e?.body?.error ?? '') {
    case 'ALREADY_DECIDED':
      return 'Someone already decided this one. The list has been refreshed.';
    case 'NO_SELF_APPROVAL':
      return 'You cannot decide your own application.';
    case 'NOT_FOUND':
      return 'That application is no longer there. The list has been refreshed.';
    default:
      break;
  }
  if (e?.status === 401) return 'Your session has expired. Sign out and back in; nothing changed.';
  if (e?.status === 403) return 'This account is not allowed to decide applications.';
  if (e?.status === undefined) return 'No connection. Nothing changed; try again when you are back online.';
  return 'That did not go through. Nothing changed; please try again.';
}

function Detail({ icon, value }: { icon: React.ReactNode; value: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
      {icon}
      <Text style={{ flex: 1, fontSize: FontSize.sm, color: Colors.textSecondary }}>{value}</Text>
    </View>
  );
}

function ApplicationCard({
  item,
  busy,
  onDecide,
}: {
  item: PendingApplication;
  busy: boolean;
  onDecide: (decision: 'approve' | 'reject') => void;
}) {
  const [confirming, setConfirming] = useState<'approve' | 'reject' | null>(null);

  return (
    <Card>
      <View style={{ gap: Spacing.md }}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm }}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text
              style={{
                fontSize: FontSize.lg,
                fontFamily: Fonts.sansSemiBold,
                color: Colors.textPrimary,
              }}>
              {item.full_name}
            </Text>
            <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted }}>
              {item.status === 'invited' ? 'Invited by the team' : 'Asked for access'}
            </Text>
          </View>
          <Pill tone="brand">{item.credential}</Pill>
        </View>

        <View style={{ gap: Spacing.xs }}>
          <Detail icon={<Mail size={15} color={Colors.textMuted} />} value={item.email} />
          <Detail
            icon={<BadgeCheck size={15} color={Colors.textMuted} />}
            value={
              item.npi
                ? `NPI ${item.npi}${item.license_state ? ` · licensed in ${item.license_state}` : ''}`
                : 'No NPI given'
            }
          />
          <Detail
            icon={<MapPin size={15} color={Colors.textMuted} />}
            value={item.specialty || 'No specialty given'}
          />
          <Detail
            icon={<Building2 size={15} color={Colors.textMuted} />}
            value={item.institution || 'No hospital or practice given'}
          />
        </View>

        {confirming === 'approve' ? (
          <View style={{ gap: Spacing.sm }}>
            <Text style={{ fontSize: FontSize.sm, lineHeight: 19, color: Colors.textSecondary }}>
              {`Approving lets ${item.full_name} sign off on wording that patients read. Their name goes on every connection they approve.`}
            </Text>
            <Button
              label={`Yes, approve ${item.full_name}`}
              onPress={() => onDecide('approve')}
              loading={busy}
              disabled={busy}
            />
            <Button label="Not yet" variant="ghost" onPress={() => setConfirming(null)} disabled={busy} />
          </View>
        ) : confirming === 'reject' ? (
          <View style={{ gap: Spacing.sm }}>
            <Text style={{ fontSize: FontSize.sm, lineHeight: 19, color: Colors.textSecondary }}>
              {`Turning down ${item.full_name} closes their request. They can be invited again later, but this list will not show them.`}
            </Text>
            <Button
              label="Yes, turn down"
              variant="danger"
              onPress={() => onDecide('reject')}
              loading={busy}
              disabled={busy}
            />
            <Button label="Go back" variant="ghost" onPress={() => setConfirming(null)} disabled={busy} />
          </View>
        ) : (
          <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
            <Button
              label="Approve"
              onPress={() => setConfirming('approve')}
              disabled={busy}
              style={{ flex: 1 }}
            />
            <Button
              label="Turn down"
              variant="secondary"
              onPress={() => setConfirming('reject')}
              disabled={busy}
              style={{ flex: 1 }}
            />
          </View>
        )}
      </View>
    </Card>
  );
}

export default function Applications() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: APPLICATIONS_KEY,
    queryFn: fetchApplications,
    staleTime: 15_000,
  });

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: 'approve' | 'reject' }) =>
      decideApplication(id, decision),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: APPLICATIONS_KEY });
    },
    onError: (err) => {
      setError(decisionError(err));
      // A race means the list is stale, so refresh it whatever went wrong.
      qc.invalidateQueries({ queryKey: APPLICATIONS_KEY });
    },
  });

  const items = list.data?.items ?? [];

  // isLoading is false during a background refetch (TanStack v5), so the
  // buttons gate on the mutation too — otherwise they stay live on a row that
  // was already decided.
  const busy = decide.isPending;

  return (
    <Screen
      gap={Spacing.md}
      refreshControl={
        <RefreshControl
          refreshing={list.isFetching && !list.isLoading}
          onRefresh={() => list.refetch()}
          tintColor={Colors.primary}
        />
      }>
      {error ? (
        <Text style={{ fontSize: FontSize.sm, color: Colors.danger, lineHeight: 19 }}>{error}</Text>
      ) : null}

      {list.isLoading ? (
        <View style={{ paddingVertical: Spacing.xxl, alignItems: 'center' }}>
          <ActivityIndicator color={Colors.primary} />
        </View>
      ) : list.error ? (
        <View style={{ gap: Spacing.md, paddingVertical: Spacing.xl }}>
          <Text style={{ fontSize: FontSize.md, color: Colors.textSecondary, lineHeight: 21 }}>
            Could not load applications. Pull down to try again.
          </Text>
        </View>
      ) : items.length === 0 ? (
        <View style={{ gap: 6, paddingVertical: Spacing.xxl }}>
          <Text
            style={{ fontSize: FontSize.lg, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
            Nothing waiting
          </Text>
          <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, lineHeight: 19 }}>
            New requests from clinicians show up here.
          </Text>
        </View>
      ) : (
        items.map((item) => (
          <ApplicationCard
            key={item.id}
            item={item}
            busy={busy}
            onDecide={(decision) => decide.mutate({ id: item.id, decision })}
          />
        ))
      )}
    </Screen>
  );
}
