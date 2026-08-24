# Coding sheet templates

Two CSVs matching the `incident` and `article` tables in `db/schema.sql`. Each carries one
example row, marked `DELETE ME`, showing the expected format for the awkward columns
(dates, enums, `make_source`).

Coders work in a copy, never in the template. Column meanings are in `CODEBOOK.md` —
sections 1 and 2 respectively.

Three columns are **not** for human coders to fill: `headline_names_make`,
`headline_names_make_strict`, and `body_names_make` are produced mechanically by
`src/build_dataset.py` from the frozen lexicon (Protocol §8.1). They are absent from
these templates on purpose. A coder who knows the hypothesis should not be deciding the
primary outcome.
