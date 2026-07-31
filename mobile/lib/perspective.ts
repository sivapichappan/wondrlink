/**
 * Who the app is talking ABOUT.
 *
 * A caregiver account is held by one person and is about another. Onboarding
 * asks which it is and stores it, and then nothing read it back — so every
 * screen kept addressing the holder as the patient. Someone managing their
 * mother's care was asked to "Add my medical details" and how "you've" felt.
 *
 * WHAT THIS DOES NOT COVER. Copy about the ACCOUNT stays second person for
 * everyone: the password is the holder's, the account being deleted is the
 * holder's, the privacy rights are the holder's. Only copy about the PATIENT
 * moves. Getting that backwards is how you end up telling a caregiver their
 * mother can delete her password.
 *
 * CONJUGATION IS THE TRAP. "You have felt" and "Mary has felt" take different
 * verbs, so any helper that substitutes a name into an arbitrary sentence
 * produces "Mary have felt" eventually. This one only ever yields THEY, which
 * conjugates identically to YOU ("you've felt" / "they've felt", "you are" /
 * "they are"). The name appears only in possessive position, where no verb
 * follows and nothing can disagree: "Mary's medical details".
 */

import { useQuery } from '@tanstack/react-query';

import type { CheckAcknowledgementResponse } from '@shared/types';
import { checkAcknowledgement } from './api/consent';

export interface Perspective {
  /** True when the holder is caring for someone else. */
  isCaregiver: boolean;
  /** The patient's first name, when known. */
  name: string | null;
  /** Subject pronoun: "you" | "they". Safe before any verb. */
  subject: string;
  /** Object pronoun: "you" | "them". */
  object: string;
  /** Possessive determiner: "your" | "their". Never a name — safe anywhere. */
  possessive: string;
  /** Capitalised possessive, for the start of a sentence or a title. */
  Possessive: string;
  /** Possessive preferring the NAME: "your" | "Mary's" | "their".
   *  Only valid immediately before a noun. */
  possessiveNamed: string;
  /** Capitalised form of the above. */
  PossessiveNamed: string;
  /** "you've" | "they've" — both take the same participle. */
  subjectHave: string;
  /** "you're" | "they're" — both take the same participle. */
  subjectAre: string;
  /** The ACCOUNT HOLDER's first name: who to greet. On a caregiver account this
   *  is the caregiver, so the home screen greets the person actually holding
   *  the phone rather than the patient it is about. */
  holderFirstName: string | null;
  /** Title-cased label for a section about the patient: "My Care" | "Mary's Care". */
  titleFor: (noun: string) => string;
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function perspectiveFrom(ack: CheckAcknowledgementResponse | undefined): Perspective {
  const isCaregiver = ack?.perspective === 'caregiver';
  const name = (ack?.patient_name ?? '').trim() || null;

  const possessive = isCaregiver ? 'their' : 'your';
  // A name is only ever used where a noun follows it, so no verb can disagree.
  const possessiveNamed = isCaregiver ? (name ? `${name}'s` : 'their') : 'your';

  return {
    isCaregiver,
    name,
    subject: isCaregiver ? 'they' : 'you',
    object: isCaregiver ? 'them' : 'you',
    possessive,
    Possessive: capitalise(possessive),
    possessiveNamed,
    PossessiveNamed: capitalise(possessiveNamed),
    subjectHave: isCaregiver ? "they've" : "you've",
    subjectAre: isCaregiver ? "they're" : "you're",
    holderFirstName: (ack?.account_holder_name ?? '').trim().split(' ')[0] || null,
    // "My Care" reads wrong on a caregiver account; "Mary's Care" reads right,
    // and "Their Care" is the fallback when the name is not known yet.
    titleFor: (noun: string) =>
      isCaregiver ? `${name ? `${name}'s` : 'Their'} ${noun}` : `My ${noun}`,
  };
}

/**
 * Read the perspective anywhere. Shares the acknowledgement query the root
 * gate already runs on every launch, so this costs no extra request.
 */
export function usePerspective(): Perspective {
  const { data } = useQuery({
    // Same key the root gate already uses, so this shares its cached result
    // instead of issuing a second request on every screen.
    queryKey: ['acknowledgement'],
    queryFn: checkAcknowledgement,
    staleTime: 60_000,
  });
  return perspectiveFrom(data);
}
