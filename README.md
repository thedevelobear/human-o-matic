# human-o-matic
Programmed drum MIDI sounds robotic, and existing tools mostly fix that with blind randomization. This MCP server re-performs a MIDI file section by section and humanizes the MIDI based on the instrument type.

The plan, the decisions behind it and the milestone status are in [`docs/`](docs/README.md).

## Development
Needs [uv](https://docs.astral.sh/uv/), which provides Python 3.12.

```sh
uv sync                  # install
uv run ruff check        # lint
uv run ruff format       # format
uv run pyright           # types
uv run pytest            # tests
```

[`AGENTS.md`](AGENTS.md) has the full workflow for people and coding agents.
