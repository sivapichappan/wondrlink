# connection_map — physician-attested knowledge graph (SPEC-connection-map.md).
#
# Imported bare (`from connection_map import ...`) because api/index.py puts
# lib/ on sys.path. Phase 1 ships vocabulary + corpus tooling only; there is
# deliberately NO runtime code path until Phase 7, and nothing in this package
# may ever import from learning_loop (spec §0 rule 2, acceptance #27).
