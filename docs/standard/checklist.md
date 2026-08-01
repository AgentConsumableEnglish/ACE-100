---
"@type": HowTo
name: The checklist
description: This procedure checks a document against the ACE-100 rules before review.
isPartOf: docs/standard/README.md
---

# The checklist

Run `tools/check.sh` and `tools/lint.py` first. Then do these checks in the given sequence. Stop and correct the document at each failed check.

1. Function words: make sure that each one is in the function core (ACE 1.1).
2. Content words: make sure that no replacements-table word occurs (ACE 1.3).
3. Names: make sure that each item keeps one name in all documents (ACE 1.10).
4. Identifiers: make sure that each identifier is backticked (ACE 1.5).
5. Verbs: make sure that all verbs use simple tenses and the active voice (ACE 3.2, 3.6).
6. Modality: make sure that "would" occurs only for counterfactual conditions (ACE 3.7).
7. Sentences: count the words against the applicable limit (ACE 5.1, 6.1).
8. Paragraphs: make sure that each paragraph has one topic and five sentences maximum (ACE 6.5, 6.6).
9. Safety: make sure that each risk has a warning or a caution (Section 7).
10. Notes: remove the notes, and make sure that the procedure stays complete (ACE 5.5).
11. Type: make sure that the document has one correct type, and a genre where applicable (ACE 12.1, 12.5).
12. Verbatim data: make sure that structured data stays in its exact form (ACE 10.6).
13. Size: count the body lines against the limit (ACE 15.1).
14. Division: make sure that a reader with one question opens one document (ACE 15.5).
15. Links: make sure that each link points to a file and operates (ACE 14.5).
16. Backticked paths: make sure that each backticked repository path resolves (ACE 14.9).
17. Paths: make sure that no load-bearing path moved (ACE 14.8).
18. Parts: make sure that each part keeps the properties of its source (ACE 15.2).
19. Index: make sure that the index of the directory lists the document (ACE 11.6).
20. Exemptions: make sure that each deviation has `exempt` and a ledger row (ACE 17.7).
