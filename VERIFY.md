# Checking this yourself

Everything here has a date on it. This page says how to re-check each kind of claim.

## Method

Claims got collected with a URL attached, then the load-bearing ones were re-opened against the primary source one at a time. Roughly 20 went through that before publishing:

- 15 confirmed, several verbatim.
- 3 wrong. The worst was a set of real benchmark numbers filed under the wrong experiment: exo's 49.3 → 39.7 tok/s figures come from a cluster of M4 Pro machines running LLaMA 3.2 3B, not from the DGX Spark and M3 Ultra pairing they had been attached to. Also, SkyPilot ships 16 admin policy examples, not 13.
- 2 not checkable from outside, now flagged in place rather than asserted.

Every wrong one had a real, working URL attached the whole time. A citation is not a check.

Don't trust a summary of a page for anything date-bearing. A summarized read of the SkyPilot release notes gave v0.13.0 as July 2025; the API gives 2026-07-22T19:30:02Z.

Rows are therefore in one of two states, and the difference matters:

- **Hand-checked.** The source was opened and the sentence read. Every quoted limitation in the tables is this kind, as are all dates, prices and version numbers.
- **Not checkable.** Said so in place. LocalScore's total result count and Strix Halo's street price are the current examples.

If you're about to spend money or a weekend on the strength of a row here, open its link.

## Staleness

Facts in this category rot in weeks. Between 2026-08-31 and 2026-09-05, while this was being put together: NVIDIA shipped a cross-vendor router that includes Macs, Perplexity shipped hybrid local/cloud on Apple silicon, and a tool listed here as spanning macOS turned out to have dropped macOS nine months earlier. Three of the seven entries in [CORRECTIONS.md](CORRECTIONS.md) are things that moved or surfaced inside one week.

So: every row carries a check date, a row older than 90 days should be treated as unverified rather than true, and star counts are the least useful number on the page.

## Stars, dates, licenses

No auth needed for public repos.

```bash
curl -s https://api.github.com/repos/OWNER/REPO \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['full_name'], d['stargazers_count'], d['created_at'][:10], d['pushed_at'][:10], d['open_issues_count'])"
```

Everything in the map at once:

```bash
for r in AlexsJones/llmfit skypilot-org/skypilot exo-explore/exo ollama/ollama \
         gpustack/gpustack NVIDIA/Personal-AI-Router mostlygeek/llama-swap \
         BerriAI/litellm dstackai/dstack cjpais/LocalScore ggml-org/llama.cpp ml-explore/mlx; do
  curl -s "https://api.github.com/repos/$r" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['full_name']:32s} {d['stargazers_count']:>7} {d['pushed_at'][:10]}\")"
done
```

## Did a feature actually ship

Not from a blog post or a comparison article. In order: release notes for version and date, reference docs for the exact option name, merge commit if contested.

For "SkyPilot can cap hourly spend": the option is `resources.max_hourly_cost`, it's in the YAML spec, it shipped in v0.13.0.

- https://github.com/skypilot-org/skypilot/releases/tag/v0.13.0
- https://docs.skypilot.ai/en/latest/reference/yaml-spec.html

## Is a limitation real

Quote the project's own words or don't claim it. PAIR's README:

> "PAIR routes each independent request to one node. It does not pool GPU memory, combine GPUs into a
> larger logical GPU, shard one model across machines, or split an in-flight inference request
> between nodes."

## Is anyone actually asking for it

Reactions on issues beat headlines. Sort by reactions, not recency:

```bash
curl -s "https://api.github.com/search/issues?q=repo:OWNER/REPO+is:issue+TERM+in:title&sort=reactions&order=desc" \
  | python3 -c "
import sys,json
for i in json.load(sys.stdin)['items'][:10]:
    print(i['reactions']['total_count'], i['state'], i['title'], i['html_url'])
"
```

A request at single digits after six months is not latent demand.

## Hardware and prices

Vendor spec pages only, and note that prices move without announcement — the DGX Spark went from $3,999 to $4,699 on 2026-02-23. For speed, prefer a measured tok/s on the exact model and quant you care about over any vendor number or calculator.

## Funding and pricing

Primary sources only. Aggregators get the wrong company often enough to matter — [CORRECTIONS.md](CORRECTIONS.md) entry 5 is a funding figure belonging to an unrelated business with a similar name.

## Found an error

Open an issue: the claim, the primary source that contradicts it, your check date.
