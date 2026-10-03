# Remember writing defaults

Read for defaults requests and new article intake. Personal defaults are local to
this writing workspace; team defaults are portable scoped Hub context records.

```text
... defaults show
... defaults show --id <article>
... defaults set --scope personal --key audience --value "Platform engineers"
... defaults set --scope team --key review_folder --value <canonical-folder-url>
... defaults reset --scope personal --key audience
```

Keys: author, audience, blog_type (announcement/tutorial/architecture/performance/
comparison/story), review_folder, voice. Show value and scope, and explain any
conflict or unavailable profile before applying it. Refresh the selected Hub to
see other members' defaults; offline cached values are labeled.

Precedence: explicit request → saved article selection → personal → team → generic.
Existing article voice, pins, brief, and preferences stay selected when defaults
change. `article create` fills missing options automatically and records audience,
blog type and review folder in `writing_preferences`; explicit `--author`,
`--audience`, `--blog-type`, `--review-folder`, `--profile`, `--voice` or `--tone`
override defaults. Imported draft voice is preserved unless explicitly selected.
Use resolved values in the brief and writing task; never silently restyle old work.

A personal voice value is JSON `{"profile_id":"<local-id>","revision":1}`.
For a team voice, first explicitly share the chosen profile and use the returned
JSON `{"item":"<shared-item>","revision":"<shared-revision>"}`; its dependency
is retained. Creation projects that exact profile locally for a different member.
Do not share personal settings, machine paths, or credentials as part of a draft.
A chosen author/voice may of course appear in the article explicitly created with it.

Team conflicts require resolution of the identified records before changing that
key. Reset retires the team default; history remains. A saved folder is a preference,
not proof of current access or permission to broaden an audience.
