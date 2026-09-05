# How to check everything here yourself

Every claim in this repo carries a `verified` date. This page tells you how to re-check each class of
claim, so that nothing here has to be taken on trust and so that you can tell how stale a row is
before you act on it.

## The staleness policy

**Facts in this category decay in weeks.** Between 2026-08-31 and 2026-09-05, while this research was
being done: NVIDIA published a cross-vendor router that includes Macs, Perplexity shipped hybrid
local/cloud execution on Apple silicon, and a fleet tool I had listed as spanning macOS turned out to
have dropped macOS workers nine months earlier. Three of the six entries in
[CORRECTIONS.md](CORRECTIONS.md) are things that changed or were discovered inside one week.

Rules I hold myself to, and that you should hold this repo to:

1. Every factual row states the date it was last checked.
2. A row more than 90 days old should be treated as unverified, not as true.
3. Star counts and funding figures are the least useful and most volatile numbers here. They are
   included only where adoption is the actual claim being made.
4. A "does not do" claim is only worth stating if it comes from the project's own documentation.
   Absence of a feature in a blog post is not evidence of its absence in the product.

## Star counts, creation dates, licenses

The GitHub API needs no authentication for public repositories.

```bash
curl -s https://api.github.com/repos/OWNER/REPO | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['full_name'], d['stargazers_count'], d['created_at'][:10], d['pushed_at'][:10], d['open_issues_count'])"
```

To re-check every repo in the map at once:

```bash
for r in AlexsJones/llmfit skypilot-org/skypilot exo-explore/exo ollama/ollama \
         gpustack/gpustack NVIDIA/Personal-AI-Router mostlygeek/llama-swap \
         BerriAI/litellm dstackai/dstack cjpais/LocalScore ggml-org/llama.cpp ml-explore/mlx; do
  curl -s "https://api.github.com/repos/$r" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['full_name']:32s} {d['stargazers_count']:>7} {d['pushed_at'][:10]}\")"
done
```

## Whether a feature actually shipped

Do not trust a blog post, a roadmap, or a comparison article. Check, in this order:

1. **The release notes**, for a version number and a date.
   `https://github.com/OWNER/REPO/releases`
2. **The reference documentation**, for the exact option name and its semantics.
3. **The merge commit**, if the feature is contested.
   `https://api.github.com/search/issues?q=repo:OWNER/REPO+TERM+in:title`

Worked example, for the claim that SkyPilot can cap hourly spend: the option is
`resources.max_hourly_cost`, it appears in the YAML spec reference, and it shipped in v0.13.0.

- https://github.com/skypilot-org/skypilot/releases/tag/v0.13.0
- https://docs.skypilot.ai/en/latest/reference/yaml-spec.html

## Whether a limitation is real

Quote the project's own words. Worked example, for NVIDIA PAIR's scheduler, from its README:

> "PAIR routes each independent request to one node. It does not pool GPU memory, combine GPUs into a
> larger logical GPU, shard one model across machines, or split an in-flight inference request
> between nodes."

> "It does not consider GPU model, available memory, model warmness, or how expensive a request
> looks."

- https://github.com/NVIDIA/Personal-AI-Router

## Whether anybody is actually asking for something

Reaction counts on issues are a better demand signal than article headlines. Sort by reactions, not
by recency:

```bash
curl -s "https://api.github.com/search/issues?q=repo:OWNER/REPO+is:issue+TERM+in:title&sort=reactions&order=desc" \
  | python3 -c "
import sys,json
for i in json.load(sys.stdin)['items'][:10]:
    print(i['reactions']['total_count'], i['state'], i['title'], i['html_url'])
"
```

A feature request sitting at single-digit reactions after six months is not latent demand. This is
the check that most 'obvious gap in the market' claims fail, including several of mine.

## Hardware numbers

Use the vendor's own specification page for memory bandwidth, capacity, and price, and note that
prices change without announcement: the DGX Spark moved from $3,999 to $4,699 on 2026-02-23.

For local decode speed, bandwidth is the number that matters more than raw FLOPS. Prefer a measured
tokens-per-second figure on the specific model and quantization you care about over any vendor claim
or any calculator.

## Pricing and funding

Primary sources only: the vendor's own pricing page, the company's own announcement, or the press
release. Secondary aggregators are frequently wrong about which company they are describing — see
[CORRECTIONS.md](CORRECTIONS.md) entry 4 for a case where a widely-cited funding figure belonged to an
unrelated company with a similar name.

## If you find an error

Open an issue with the claim, the primary source that contradicts it, and your check date. See the
end of [CORRECTIONS.md](CORRECTIONS.md).
