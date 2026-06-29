# RAW NOTES — post: adding a custom background image to a Hugo/PaperMod site (and the path bug that breaks it)

(Raw notes. /newpost turns these into a finished post in my voice.)

## Images for post
- Hugo logo: `/images/posts/hugo-logo.svg` — place at top
- EFT background (already in site): `/images/eft-bg.jpg` — reference it inline when explaining the image choice

![Hugo](/images/posts/hugo-logo.svg)

## Goal
- Apply a full-page background image (EFT wallpaper) to every page of the Hugo blog
- Readable text on top, image visible but not distracting
- Works on GitHub Pages (project page, served from a subdirectory)

## Approach: CSS in assets/css/extended/
- PaperMod loads any CSS from `assets/css/extended/` as overrides after core theme CSS
- Created `assets/css/extended/custom.css`

## First attempt — broke on GitHub Pages
- Put background-image in custom.css:
  ```css
  body {
    background-image: url('/images/eft-bg.jpg');
  }
  ```
- Locally: looked fine. On GitHub Pages: just black.
- Root cause: `/images/eft-bg.jpg` is an ABSOLUTE path from the domain root
- On a project page at `/reponame/`, the image lives at `/reponame/images/eft-bg.jpg`
- Browser tried `/images/eft-bg.jpg` → 404 → fallback to dark background-color → black

## The fix: relURL in a Hugo template partial
- Can't use Hugo template functions in `.css` files — they're not processed as templates
- PaperMod provides a hook: `layouts/_partials/extend_head.html` — loaded into `<head>` on every page
- Created that file with an inline `<style>` block using Hugo's `relURL`:
  ```html
  <style>
    body {
      background-image:
        linear-gradient(rgba(0,0,0,0.58), rgba(0,0,0,0.58)),
        url('{{ "images/eft-bg.jpg" | relURL }}') !important;
    }
  </style>
  ```
- `relURL` generates the correct path relative to the site root, including any subdirectory prefix
- Verified: Hugo CI build injects the right path via `--baseURL` from `configure-pages`

## Gradient overlay instead of body::before
- First version used `body::before { position: fixed; z-index: -1; background: rgba(0,0,0,0.6); }`
- Problem: z-index stacking with body's own background gets weird. Showed up as black again.
- Better approach: CSS multi-layer background — stack a gradient directly on the image:
  ```css
  background-image:
    linear-gradient(rgba(0,0,0,0.58), rgba(0,0,0,0.58)),
    url('...');
  ```
- The gradient IS the overlay. No pseudo-elements, no z-index fights.

## Making content areas transparent so the image shows through
- PaperMod sets `body { background: var(--theme) }` which is a solid color in dark mode
- Override: `[data-theme="dark"] { --theme: transparent !important; }`
- For cards/header, set rgba backgrounds with backdrop-filter blur:
  ```css
  .header {
    background: rgba(13, 13, 14, 0.82) !important;
    backdrop-filter: blur(10px);
  }
  .post-entry {
    backdrop-filter: blur(4px);
  }
  ```

## Image: 4K EFT wallpaper
- 3840x2160 from wallpapercave.com
- Stored in `static/images/eft-bg.jpg` → Hugo copies it to `public/images/eft-bg.jpg`
- CSS: `background-size: cover; background-position: center top; background-attachment: fixed`
- `cover` ensures it always fills the viewport regardless of screen size, crops cleanly
- `fixed` keeps the image stationary while content scrolls (parallax-like effect)

## Tuning tip
- Overlay opacity is `0.58` — bump it up toward `0.75` if text is hard to read,
  lower it toward `0.4` if you want more image visible
- Change the single rgba value in extend_head.html
