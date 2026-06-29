# RAW NOTES — post: deploying a Hugo blog to GitHub Pages (the things that actually trip you up)

(Raw notes. /newpost turns these into a finished post in my voice.)

## The setup
- Hugo blog, PaperMod theme (as a git submodule), GitHub Actions workflow
- Repo named: unemployedblog.github.io under username dwaynethecock69420
- Target: auto-deploy on push to main

## Problem 1: clicking any post link gave an error (404)
- Homepage loaded, post links didn't work
- Root cause: GitHub Pages source was set to "Deploy from a branch" not "GitHub Actions"
  - Branch deploy serves raw repo files — no HTML, no built site
  - GitHub Actions deploy runs the build workflow and serves the output
- Fix: Settings → Pages → Build and deployment → Source → GitHub Actions

## Problem 2: repo name is NOT username.github.io
- Important distinction:
  - User page: repo named `<username>.github.io` → served at `https://<username>.github.io/`
  - Project page: any other repo name → served at `https://<username>.github.io/<reponame>/`
- My repo `unemployedblog.github.io` is NOT the same as `dwaynethecock69420.github.io`
- So it's served from a subdirectory: `https://dwaynethecock69420.github.io/unemployedblog.github.io/`

## Why subdirectory hosting matters for asset paths
- Hardcoded paths like `/images/eft-bg.jpg` resolve to the DOMAIN root, not the site root
- On a project page: `/images/eft-bg.jpg` → `dwaynethecock69420.github.io/images/eft-bg.jpg` (WRONG)
- Should be: `dwaynethecock69420.github.io/unemployedblog.github.io/images/eft-bg.jpg`
- Hugo's `relURL` template function fixes this — generates the correct path based on baseURL
- The GitHub Actions workflow uses `--baseURL "${{ steps.pages.outputs.base_url }}/"` which
  automatically sets the right base (including subdirectory) at build time

## The correct Hugo Actions workflow structure
- `actions/configure-pages@v5` → gets the correct base_url including any subdirectory
- `hugo --gc --minify --baseURL "${{ steps.pages.outputs.base_url }}/"` → uses it
- `actions/upload-pages-artifact@v3` → uploads public/
- `actions/deploy-pages@v4` → deploys to Pages
- Needs permissions: `contents: read`, `pages: write`, `id-token: write`

## Submodule gotcha
- PaperMod as a git submodule requires `submodules: recursive` in the checkout step
- Without it, the themes/ directory is empty and the build fails with "theme not found"
  ```yaml
  - uses: actions/checkout@v4
    with:
      submodules: recursive
      fetch-depth: 0
  ```

## Checking if the workflow ran
- GitHub repo → Actions tab → look for green check or red ✗
- If it shows a yellow dot it's still running
- If Pages shows the wrong content, check Actions first before digging into config

## The one-line check for deployment mode
- Settings → Pages → Build and deployment
- Source should say "GitHub Actions" NOT "Deploy from a branch"
- This is the most common setup mistake for Hugo on GitHub Pages
