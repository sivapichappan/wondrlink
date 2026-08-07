/**
 * Everything that knows what an answer's text looks like.
 *
 * Sage answers are markdown. Two places need to see past the markup: the
 * select-text sheet, which wants something a person can paste into a message to
 * their daughter or hand to their oncologist, and the answer card, which splits
 * an answer into its labelled sections so it can be skimmed.
 *
 * Both are pure string functions on purpose. They run on every render of every
 * message, they have to be safe on an empty string, and they must never throw
 * on whatever the model happened to emit.
 */

/** One labelled block of an answer. */
export interface AnswerSection {
  label: string;
  body: string;
}

export interface SplitAnswer {
  /** The direct answer, before any section heading. May be empty. */
  lead: string;
  sections: AnswerSection[];
}

const HEADING = /^[ \t]*#{1,6}[ \t]+/;
const SECTION_HEADING = /^[ \t]*##[ \t]+(.+?)[ \t]*$/;

/**
 * Markdown to something worth pasting.
 *
 * Line-oriented and whitespace-preserving. A blanket regex sweep over the whole
 * string is how the prompt files lost the indentation of their JSON examples
 * (.claude/rules/prompt-files.md); the same mistake here would flatten a nested
 * bullet list into one that reads as unrelated points.
 *
 * Citation markers like [1] are deliberately left alone. They are not links,
 * they are the answer's evidence, and someone showing this to a clinician wants
 * them.
 */
export function toPlainText(markdown: string): string {
  if (!markdown) return '';

  const lines = markdown.split('\n').map((line) => {
    // Keep the heading's words, drop its hashes. The label is a sentence the
    // reader wants; the "##" is markup they never asked to see.
    let out = line.replace(HEADING, '');

    // [label](url) -> label (url). The URL survives because a link a patient
    // copies is usually a link they meant to send on.
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '$1 ($2)');

    // Emphasis. The delimiters must hug non-space so "5 * 3" and snake_case
    // survive, and bold runs first so **x** does not leave a stray asterisk.
    out = out.replace(/\*\*(\S(?:[^*]*\S)?)\*\*/g, '$1');
    out = out.replace(/__(\S(?:[^_]*\S)?)__/g, '$1');
    out = out.replace(/(^|[\s(])\*(\S(?:[^*]*\S)?)\*(?=[\s).,;:!?]|$)/g, '$1$2');
    out = out.replace(/(^|[\s(])_(\S(?:[^_]*\S)?)_(?=[\s).,;:!?]|$)/g, '$1$2');

    // Inline code.
    out = out.replace(/`([^`]+)`/g, '$1');

    return out.replace(/[ \t]+$/, '');
  });

  // Collapse runs of blank lines, but keep one: the paragraph breaks are the
  // only structure plain text has left.
  const collapsed: string[] = [];
  for (const line of lines) {
    if (line === '' && collapsed[collapsed.length - 1] === '') continue;
    collapsed.push(line);
  }

  return collapsed.join('\n').trim();
}

/**
 * Split an answer into its lead sentence and its labelled sections.
 *
 * Degrades to silence: an answer with no "## " headings comes back as all lead
 * and no sections, which is exactly how every answer already stored in the
 * database looks, and how the card renders them today. That is the whole reason
 * the split lives here rather than in the markdown renderer.
 */
export function splitAnswer(markdown: string): SplitAnswer {
  const empty: SplitAnswer = { lead: markdown ?? '', sections: [] };
  if (!markdown || !markdown.includes('#')) return empty;

  const lines = markdown.split('\n');
  const leadLines: string[] = [];
  const sections: AnswerSection[] = [];
  let current: { label: string; body: string[] } | null = null;

  for (const line of lines) {
    const match = SECTION_HEADING.exec(line);
    if (match) {
      if (current) sections.push({ label: current.label, body: current.body.join('\n').trim() });
      current = { label: match[1].trim(), body: [] };
    } else if (current) {
      current.body.push(line);
    } else {
      leadLines.push(line);
    }
  }
  if (current) sections.push({ label: current.label, body: current.body.join('\n').trim() });

  if (!sections.length) return empty;

  // A label with nothing under it is a truncated answer, not a section. Fold it
  // back into whatever came before as plain text so the card shows a slightly
  // short answer instead of a heading pointing at blank space.
  const kept: AnswerSection[] = [];
  let orphanedLabels: string[] = [];
  for (const section of sections) {
    if (!section.body) {
      orphanedLabels.push(section.label);
      continue;
    }
    kept.push(section);
  }
  if (orphanedLabels.length) {
    const tail = orphanedLabels.join(' ');
    if (kept.length) {
      kept[kept.length - 1] = {
        ...kept[kept.length - 1],
        body: `${kept[kept.length - 1].body}\n\n${tail}`.trim(),
      };
    } else {
      return { lead: `${leadLines.join('\n')}\n\n${tail}`.trim(), sections: [] };
    }
  }

  return { lead: leadLines.join('\n').trim(), sections: kept };
}
