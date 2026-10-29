# Marketing Studio and Infographic Studio visual pilot

Scope: these two applications only. Other studio pages keep their existing appearance.
Use the existing Python/HTML/CSS/JavaScript stack and system fonts; add no runtime libraries.

The launcher is a calm two-by-two collection of studio objects, with compact readiness
indicators and expandable repository details. The sidebar and command bar form a single
application shell. Infographic Studio uses the same shell, a clear story-selection surface
and a paper preview on an opaque canvas. Existing workflow, permissions, saved content,
provider disclosures and approval checkpoints are preserved.

Light roles: canvas `#f5f5f7`, paper `#ffffff`, ink `#191b20`, secondary text `#606570`,
diffused chrome near white. Dark roles: canvas `#141519`, paper `#202227`, ink `#f4f5f7`,
secondary text `#b3b7c2`, diffused chrome near `#25272d`. Retain the existing studio accents.
System type has distinct title, object-title, body and metadata sizes. No font downloads.

Material map: diffusion on navigation, toolbars and transient controls; opaque cards,
forms and documents. Only object cards, selected navigation and compact commands receive
subtle depth. No wallpaper, simulated desktop controls or glass behind reading text.

The `data-pilot="liquid"` opt-in is set only for Marketing Studio and Infographic Studio.
Reduced transparency/stronger contrast use solid chrome; reduced motion removes movement.
Verify desktop and phone, both appearances, keyboard focus, long labels, modal forms,
status/recovery, 200% zoom and all existing actions. Render synthetic fixtures for review;
never expose a real document or private session link in screenshots committed to Git.
