<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Application architecture
- Keep PGARA experiment state in a shared provider above the route outlet so inputs and results survive navigation.
- Keep typed experiment requests, response validation, sample fixtures, and the replaceable HTTP service separate from visualization components so FastAPI integration does not require view rewrites.
- Use dedicated content routes for each research workspace view with unique metadata so navigation and direct links remain valid.
- Sample mode returns a fixed explicitly labeled fixture, never computed allocation or fabricated benchmark measurements; backend mode never silently falls back to sample data.
- Browser-only API requests target the configured external analysis service; no server-side service, authentication, or persistence is part of this frontend.
