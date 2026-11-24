# The liquid look

The liquid pilot began as an opt-in look for Marketing Studio and Infographic Studio. It
is now the one look of all five apps: Marketing Studio Home, Blog Studio, Presentation
Studio, Training Studio and Infographic Studio. Its tokens and component rules are the
base of `ui-kit/style.css`, and no page opts into it or out of it (`data-pilot` is gone;
`tests/test_ui_consistency.py` keeps it gone).

What it is, the rules a change keeps to and the tests that hold them are in
[the shared UI kit](ui-kit.md#the-look).

The pilot's material map still holds: diffusion only on navigation, toolbars and transient
controls; opaque cards, forms and documents; subtle depth only on object cards, selected
navigation and compact commands; no wallpaper, simulated desktop controls or glass behind
reading text. Reduced transparency and stronger contrast use solid chrome; reduced motion
removes movement. Review screenshots use synthetic fixtures; never commit a real document
or a private session link in one.
