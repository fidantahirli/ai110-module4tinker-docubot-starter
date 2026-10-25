# DocuBot Model Card

This model card is a short reflection on my DocuBot system. I filled it out after building retrieval and trying all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

---

## 1. System Overview

**What is DocuBot trying to do?**  
DocuBot answers developer questions about a project using only the project's own docs in the `docs/` folder. A normal LLM does not know what is in those docs, so it guesses. DocuBot searches the docs first, so its answers come from real text.

**What inputs does DocuBot take?**

> A question typed in the terminal, the `.md` files in the `docs/` folder (AUTH, API_REFERENCE, DATABASE, SETUP), and a `GEMINI_API_KEY` in my `.env` file for the modes that use the LLM.

**What outputs does DocuBot produce?**

> Mode 1 gives an LLM answer with no docs. Mode 2 gives the matching sections of the docs, labeled with the file name. Mode 3 gives a short LLM answer written from those sections, plus the file it used. If nothing in the docs matches, it says "I do not know based on these docs."

---

## 2. Retrieval Design

**How does your retrieval system work?**

- **Index:** `build_index` loops through every doc, lowercases the text, splits it into words, and saves each word with the list of files it appears in (once per file).
- **Chunking:** `build_chunks` cuts each doc at every heading (`"\n#"`), so each piece is one section. The 4 docs become about 40 small sections.
- **Scoring:** `score_document` goes through the question's words. It skips filler words like "the", "is" and "where" (my `STOPWORDS` list) and removes punctuation like `?`. It adds 1 for each word whose first 6 letters appear in the section. This lets "generated" match "generation".
- **Top snippets:** `retrieve` scores every section, keeps the ones that score at least `MIN_SCORE`, sorts by score (highest first, shorter section wins a tie), and returns the top 3.

**What tradeoffs did you make?**

> I picked simple over smart. Counting matching words is easy to explain, but it does not understand meaning, so it cannot match synonyms. Cutting at headings gives small, focused answers, but a section can still be long. Matching on the first 6 letters helps word forms match, but it can also match words that are not really related. Also, `build_index` builds an index, but `retrieve` currently loops over all sections instead of using it. That is fine for 4 small docs, but it would be slow for a large doc set.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**

- Naive LLM mode: always calls Gemini, but only sends my question. The docs text is passed to the function and then ignored, so the model answers from general knowledge.
- Retrieval only mode: never calls the LLM.
- RAG mode: calls Gemini only if retrieval found at least one section. If retrieval found nothing, it refuses right away without calling the LLM.

**What instructions do you give the LLM to keep it grounded?**

> The RAG prompt tells Gemini to use only the snippets it was given, not to make up functions, endpoints or settings, to reply "I do not know based on the docs I have." when the snippets are not enough, and to name the files it used.

---

## 4. Experiments and Comparisons

I ran the same questions in the three modes.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Not helpful. It said it had no context and asked me for code. | Helpful. Returned 3 AUTH.md sections, and "Token Generation" (names `generate_access_token`) was one of them, but it was third. | TODO: run in Mode 3 | Naive could not answer because it never saw the docs. |
| How do I connect to the database? | Harmful. Confident but wrong: it listed `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` and an ORM. | TODO: run in Mode 2 | Helpful. Said to use `DATABASE_URL`, gave the SQLite default and the Postgres format, mentioned `db.py`, and named DATABASE.md. | The docs only use `DATABASE_URL`. Naive made up variables. |
| Which endpoint lists all users? | Not helpful. It asked which system I meant. | TODO: run in Mode 2 | TODO: run in Mode 3 | |
| How does a client refresh an access token? | TODO | TODO | TODO | |

**What patterns did you notice?**

> Naive LLM looks impressive on the database question: it gives a long, organized answer with steps and examples. But none of it matches my docs, so a developer who followed it would set the wrong variables. On the other two questions it just asked for more context.
>
> Retrieval only is trustworthy because the text comes straight from my docs and has a file name. But it is hard to read, because it returns raw sections and I have to find the answer myself.
>
> RAG was clearly better on the database question. It gave a short, clear answer using the real names (`DATABASE_URL`, `app.db`, `db.py`) and told me which file it used.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**

> **Failure case 1 (Part 2, filler words).**  
> Question: "Where is the auth token generated?"  
> What happened: my first scoring counted every word, including "where", "is" and "the", and it matched words inside other words (like "is" inside "this"). `SETUP.md` came first with a score of 5, and `AUTH.md` was last with 4.  
> What should have happened: `AUTH.md` should come first. I fixed it by skipping a list of filler words and stripping punctuation, and after that `AUTH.md` scored 3 against 2 and 0 for the others.

> **Failure case 2 (Part 3, ties).**  
> Question: "Where is the auth token generated?"  
> What happened: after cutting the docs into sections, three AUTH.md sections scored the same, and "Token Generation", which has the real answer, came third, not first. Ties go to the shorter section, and that section is longer.  
> What should have happened: "Token Generation" should be first. It is still in the top 3, so the answer is there, but the ranking is not right. Word counting cannot tell which section is really about the question.

**When should DocuBot say “I do not know based on the docs I have”?**

> 1. When the topic is not in the docs at all, like payment processing.
> 2. When the question is off-topic, like "What is the weather today?" (I tested this one and it refused).
> 3. When the sections mention the topic but do not have the specific fact. Retrieval cannot catch this by itself, so the RAG prompt rule has to.

**What guardrails did you implement?**

> A refusal rule in `retrieve`: a section only counts if it matches at least `MIN_SCORE = 1` real (non-filler) word from the question. If no section does, `retrieve` returns nothing and DocuBot answers "I do not know based on these docs." In RAG mode this also skips the LLM call. I also limited results to the top 3 sections, and the RAG prompt tells Gemini to use only the snippets and not to make anything up.

---

## 6. Limitations and Future Improvements

**Current limitations**

1. Scoring only counts matching words. It does not understand meaning, so synonyms like "login" and "sign in" would not match.
2. `MIN_SCORE = 1` is a very low bar. A vague question that happens to share one real word with the docs will still get an answer, not a refusal.
3. Ties between sections are broken by length, which is not a good measure of which section is best.
4. Matching the first 6 letters of a word can match unrelated words, and the filler word list is one I wrote by hand, so it is not complete.
5. The index is built but not used by `retrieve`, so it would be slow on a big doc set.

**Future improvements**

1. Give rare words more weight than common ones (like TF-IDF), so a word like `AUTH_SECRET_KEY` counts more than "required".
2. Use embeddings so the search matches by meaning, not exact words.
3. Make `retrieve` use the index to find candidates, and raise `MIN_SCORE` or require a share of the question's words to match.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**

> A wrong answer about auth or the database could make a developer set up secrets or connections the wrong way. The docs can also be out of date, so even a correct answer from them could be wrong. And retrieval can miss the right section without any warning, so people who trust it too much may not notice.

**What instructions would you give real developers who want to use DocuBot safely?**

- Open the file it names and check the answer before acting, especially for secrets, auth or production databases.
- If DocuBot says "I do not know", believe it. Do not keep rewording until it gives an answer.
- Keep the docs up to date, because DocuBot can only be as right as the docs.
- Never put real secrets or API keys in the docs.

---