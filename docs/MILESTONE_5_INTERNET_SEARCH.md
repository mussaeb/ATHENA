# Milestone 5: Internet Search

ATHENA can search the web and keep the source URL next to each result.

The search calls DuckDuckGo's lite page, then fills any gap from the Wikipedia API. Both calls use the Python standard library. Results are text snippets, not a full browser.

## Commands

Show results:

```text
/web Python release
```

Answer from those results:

```text
/askweb what is the current stable Python version?
```

Use the web for ordinary questions:

```text
/webmode on
```

Turn it off:

```text
/webmode off
```

From the terminal:

```bash
python3 scripts/athena_web.py search "Python programming language" --limit 3
```

## What The Model Is Allowed To Say

A normal question does not include web results. The system prompt tells ATHENA to ask for `/askweb` or `/webmode on` when a question needs current information.

When web results are attached, the prompt includes a section named `Web search results:`. The answer should cite the URLs from that section.

## Limits

- DuckDuckGo's lite HTML can change. If it does, Wikipedia can still answer some questions, and the parser has a fixture test.
- ATHENA does not open arbitrary links, so it cannot be pointed at an address inside your network.
- Web mode plus document mode sends both result sets. On a 1536 context, keep the question specific.
