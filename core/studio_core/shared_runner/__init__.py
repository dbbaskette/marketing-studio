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

- its host modules: `workspace` (with `WorkspaceError`, the refusal a person reads),
  `home`, `hub` and `sync_guidance`. A studio either keeps them in its scripts folder under
  those names, with a `runner` package whose `__init__` puts that folder on the import
  path, as `import runner` does in each deck studio; or passes them to `for_product` as
  `MODULES`, a dict from the name to the module object, as a studio does whose own modules
  by those names are other modules (its `hub` a registry of something else, say);
- its module for the file every studio shares, `studios_config` (in the scripts folder,
  or as `runner.studios_config`), passed in by the facade of a module that writes it;
- the values each module asks for: the full product name as `PRODUCT`, the item words
  as `ITEM` and `ITEMS`, the data folder's environment variable, and any path the studio
  owns (its installer pins, its own installer). Nothing here names a product, an item
  word, a data variable or a studio's path.

A whole module reaches each host module and each fellow (another shared module) through
`studio_core.modules.host_module`: the one the studio passed in `MODULES`, else the one
imported by name, `import home` or, for a fellow, as `from runner import companion` finds
it. A part reaches its fellows through the studio's package. Nothing reaches a fellow by its
place in the core, so each process holds one object per module and a patch on it reaches
every caller. A studio that passes its modules has no `runner` package for a plain import
to find them through, so its facade makes the module with `whole_module` below, which never
imports the shared file plainly first.

`WHOLE` and `PARTS` name the modules that live here, filled in as each one arrives.
"""

WHOLE = ('brand_source', 'companion', 'research', 'agents', 'brand', 'team', 'gitstate',
         'documents')
PARTS = ('page', 'settings', 'setup', 'slides', 'upkeep', 'worker_tools', 'studio',
         'desk_chat', 'desk_migration')


def whole_module(module, name, product, **values):
    """The whole shared module `module` for one studio, as `sys.modules[name]`: what its own
    `for_product(name, product, **values)` makes, without importing the shared file plainly
    first (a plain import looks for its host modules by name)."""
    from pathlib import Path

    from studio_core.modules import fresh_module
    if module not in WHOLE:
        raise ValueError(f'{module} is not a whole module of the shared runner.')
    return fresh_module(Path(__file__).with_name(f'{module}.py'), name,
                        {'PRODUCT': product, **values})
