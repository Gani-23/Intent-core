# Distribution drafts — yours to edit and post yourself

I can't post these anywhere — they need your voice and your account. Here's a starting draft for each. Change anything that doesn't sound like you.

---

## Show HN draft

**Title:** Show HN: Intent Guard – catches when your AI coding agent does something you didn't ask for

**Body:**

Most AI agent safety tools check *who* an agent is or *what it's allowed to touch* — credentials, permissions, identity. Intent Guard checks something different: does what the agent actually did still match what you told it to do?

That distinction matters because an agent with perfectly valid permissions can still go off-script — the tool that would've caught Replit deleting a production database mid code-freeze isn't an identity or access product, it's one that compares stated intent against observed action.

It runs two ways:
- A GitHub Action that comments on your PRs
- A local hook for Claude Code (Cursor/Copilot support in progress)

It's open source (Apache-2.0), has a live in-browser demo with zero backend (paste a task and a command, see the verdict), and I've been dogfooding it on this repo's own PRs.

I'd genuinely like to know: does this catch anything real for you, or does it just get in the way? Both answers are useful to me.

[link to repo] · [link to the "would this have caught it" demo page]

---

## Reddit draft (r/programming, r/ClaudeAI, or similar — pick one, don't crosspost identically to several at once)

**Title:** I built a tool that checks if my AI coding agent actually did what I asked — not just what it's allowed to do

**Body:**

Been using Claude Code a lot and got nervous after reading about the Replit incident (agent deleted a production DB during an explicit code freeze). Permission systems wouldn't have caught that — the agent had valid access, it just didn't do what it was told.

So I built Intent Guard: it watches what an agent actually does in a session and checks it against what you declared at the start, flagging real mismatches (destructive commands violating a stated "read-only" constraint, etc.) rather than just checking credentials.

There's a live demo with no signup — paste a task + a command and see it evaluate live in your browser: [link]

Open source, still early, genuinely want to know if this is useful to anyone besides me. Feedback (including "this is pointless because X") is welcome.

[repo link]

---

## The one-line pitch, for anywhere else you mention it

"Most agent-safety tools check who an AI coding agent is. This checks whether what it did still matches what you asked."

---

## Where to host the demo page

`docs/index.html` is a single, self-contained file — no build step, no backend, no dependencies beyond a CDN font load. Any of these work in under five minutes:
- **GitHub Pages**: enable Pages on the `docs/` folder in repo settings.
- **Vercel/Netlify drag-and-drop**: literally drag the file onto their web upload UI.
- Link to it from the README and from the Show HN / Reddit posts above.
