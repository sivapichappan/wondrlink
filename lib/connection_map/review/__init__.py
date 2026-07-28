# connection_map.review — reviewer-facing code (SPEC-connection-map.md §5).
#
# NOTHING IN THIS PACKAGE MAY IMPORT A PATIENT MODEL. Not patient_model, not
# supabase_storage, not modeler, not question_policy, not learning_loop, not
# anything that reads patient data. §5.8 requires that rule and
# tests/test_connection_map_review_boundary.py enforces it by walking the
# import graph of every module in here.
#
# The database side of the same boundary is the sage_review role, which holds
# zero privileges on patient tables (see db.py and the migration). The import
# rule exists so a mistake is caught in CI rather than at the database, and so
# a reviewer of this code can see the boundary without reading SQL.
