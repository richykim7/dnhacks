import { readFile, writeFile } from "node:fs/promises";
const source = JSON.parse(
  await readFile(
    new URL("../../demo/pdac/papers.json", import.meta.url),
    "utf8",
  ),
);
const corpus = {
  scope: source.scope,
  question: source.research_prompt,
  cutoff: source.last_publication_date,
  papers: source.papers.map(({ candidate, category }) => ({
    title: candidate.title,
    year: candidate.year,
    doi: candidate.doi,
    category,
  })),
};
await writeFile(
  new URL("../src/corpus.json", import.meta.url),
  JSON.stringify(corpus, null, 2) + "\n",
);
