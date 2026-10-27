"""The runner modules the studios that build slides share, kept once.

Two kinds of module live here.

    WHOLE   a whole runner module. Each ends with `for_product(name, product, **values)`,
            which runs this file afresh as `sys.modules[name]` with the studio's values
            (`studio_core.modules.fresh_module`). The studio's `runner/<name>.py` is a
            facade that puts that module in its own place, so `runner.<name>` is the one
            module object every caller and every test patch sees.
    PARTS   the common part of a runner module whose rest is the studio's own. The file
            holds the definitions both studios share and ends with `NAMES` and `METHODS`;
            the studio's module binds them into itself with `studio_core.modules.bind`,
            so they read the studio module's names, its constants and its patches.

The host contract, what a studio using the shared runner gives it:

- a `runner` package whose `__init__` puts the studio's scripts folder on the import
  path, as `import runner` does in each studio today;
- in that scripts folder, the modules `workspace` (with `WorkspaceError`, the refusal a
  person reads), `home`, `hub`, `sync_guidance` and `studios_config`;
- the values each module asks for: the full product name as `PRODUCT`, the item words
  as `ITEM` and `ITEMS`, the data folder's environment variable, and any path the studio
  owns (its installer pins, its own installer). Nothing here names a product, an item
  word, a data variable or a studio's path.

A shared module imports its fellows only through the studio's package, as
`from runner import companion, settings`, and never by their place in the core, so each
process holds one object per module and a patch on it reaches every caller.

`WHOLE` and `PARTS` name the modules that live here, filled in as each one arrives.
"""

WHOLE = ('brand_source', 'companion', 'research', 'agents')
PARTS = ()
