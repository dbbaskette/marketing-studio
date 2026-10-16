"""The shared research component: harness-research for every studio, one way.

What a caller needs to know
---------------------------
    from studio_research import project, runtime        # the record, the plan, the status
    from studio_research import tools, steps             # a research worker's tools, the flow

See docs/research-component-spec.md in Marketing Studio. Standard library only; nothing here
names a studio. Each studio carries this package unchanged, recorded in vendor.json, until it
moves into the Marketing Studio core.
"""

VERSION = '1.0.0'
