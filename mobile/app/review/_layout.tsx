/**
 * Review workspace stack (SPEC-connection-map.md §5.4, adapted phone-first).
 *
 * This is now a SECTION of the app rather than a replacement for it. Reviewers
 * live in the normal app — same home, same chat, same drawer — and come here
 * from the Approvals row; a physician vouching for patient-facing wording has
 * to be able to see the product it appears in. So the gate below refuses
 * non-reviewers rather than pinning reviewers in place, and "back" leads
 * somewhere real.
 *
 * A pending applicant is refused here exactly as a stranger is: applying is not
 * being approved. The real boundary is server-side either way — every
 * /api/review/* call runs on the restricted sage_review role and answers a
 * uniform 403 to anyone whose reviewer row is not active — so this gate is UX,
 * not security.
 */

import { Redirect, Stack } from 'expo-router';

import { HeaderBack } from '@/components/common/HeaderBack';
import { Colors } from '@/constants/theme';
import { useReviewerSession } from '@/hooks/useReviewerSession';

export default function ReviewLayout() {
  const reviewer = useReviewerSession();

  if (!reviewer.isLoading && !reviewer.isReviewer) {
    return <Redirect href="/" />;
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
        headerBackTitle: 'Back',
        // Every screen here is opened STRAIGHT FROM THE DRAWER, so it is the
        // first route in this nested stack and react-navigation renders no back
        // button of its own — the route beneath sits on the PARENT stack, which
        // it will not cross. A reviewer who tapped Approvals was stuck until
        // they force-quit the app. Set on screenOptions rather than per screen
        // because any of them can be the first route depending on how it was
        // reached, and the next one added would forget. This is the same
        // HeaderBack the tools, profile and settings stacks use.
        headerLeft: () => <HeaderBack label="Back" />,
      }}>
      <Stack.Screen name="index" options={{ title: 'Review queue' }} />
      <Stack.Screen name="publish" options={{ title: 'Publish version' }} />
      <Stack.Screen name="applications" options={{ title: 'Reviewer applications' }} />
    </Stack>
  );
}
