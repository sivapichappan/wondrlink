# connection_map.extraction — literature extraction (SPEC-connection-map.md §6).
#
# Runs OFFLINE from scripts/, never in a request. Nothing here decides what a
# patient sees: every candidate it produces goes to a physician, and every
# citation it produces is verified by exact string match here AND again by a
# database trigger on insert AND once more at publication.
#
# The one rule that must never soften (§16): citation checks are exact string
# matching. Not fuzzy, not embeddings, not an LLM judge. The characteristic
# failure of this pipeline is a plausible relationship with an invented
# citation, and exact matching catches that every time.
