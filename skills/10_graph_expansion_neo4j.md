# Skill: Neo4j Legal Graph Expansion

## Goal

Use Neo4j as a graph expansion layer after first-stage retrieval.

## Important Rule

Neo4j is not the primary retriever in Phase 1.

Use Neo4j only after BM25 + dense + exact retrieval returns candidate articles.

## Graph Nodes

Use:

- `Law`
- `Article`
- `PhapdienArticle`
- `AnleCase`
- `Domain`
- `Concept`

## Relationships

Use:

```text
(Law)-[:HAS_ARTICLE]->(Article)
(Law)-[:GUIDES]->(Law)
(Law)-[:AMENDS]->(Law)
(Article)-[:RELATED_TO]->(Article)
(Article)-[:REFERENCES]->(Article)
(PhapdienArticle)-[:DERIVED_FROM]->(Article)
(AnleCase)-[:APPLIES_ARTICLE]->(Article)
(Article)-[:BELONGS_TO_DOMAIN]->(Domain)
```

## Use Cases

Use graph expansion for:

- related articles
- same law neighboring articles
- law guidance relationships
- amendment/replacement relationships
- phapdien source mapping
- multi-hop questions

## Required Modules

```text
backend/infrastructure/graph_store/neo4j_client.py
backend/indexing/build_graph_index.py
backend/retrieval/graph_expander.py
```

## Scoring

Graph expansion should apply soft boost.

Do not blindly add all graph neighbors to final output.
