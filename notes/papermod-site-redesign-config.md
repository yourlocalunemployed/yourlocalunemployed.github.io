# RAW NOTES — post: configuring PaperMod for a real portfolio blog

(Raw notes. /newpost turns these into a finished post in my voice.)

## Images for post
- Hugo logo: `/images/posts/hugo-logo.svg` — place at top or near intro
- Hugo GitHub screenshot: `/images/posts/hugo-github-screenshot.png` — place near stack section

![Hugo](/images/posts/hugo-logo.svg)

## What I was starting from
- Fresh Hugo install, PaperMod theme, placeholder hugo.toml ("Your Blog Title", "your-domain.example")
- One post, no navigation, no About/profile section, no archive
- Needed it to actually look like a portfolio blog, not a demo

## Changes made to hugo.toml
- Replaced `languageCode` with `locale = "en-AU"` (hugo.toml deprecation warning)
- Set proper title
- Added `[params.homeInfoParams]` block — PaperMod's built-in profile section on the homepage:
  ```toml
  [params.homeInfoParams]
    Title = "Name"
    Content = "One-line bio"
  ```
- Added nav menu with Posts / Tags / Archive:
  ```toml
  [[menu.main]]
    name = "Posts"
    url = "/posts/"
    weight = 1
  ```
- Enabled: ShowReadingTime, ShowCodeCopyButtons, ShowPostNavLinks, ShowBreadCrumbs, ShowToc

## The Archive page gotcha
- PaperMod needs a content file to activate the /archives/ page — it doesn't auto-generate it
- Fix: create content/archives.md with layout = "archives"
  ```yaml
  ---
  title: "Archive"
  layout: "archives"
  url: "/archives/"
  summary: "archives"
  ---
  ```
- Without this file, the Archive menu link 404s

## What homeInfoParams looks like vs profile mode
- homeInfoParams: adds a header block above the post list. Simple, no avatar needed.
- profileMode: full profile page with image, links, buttons. More setup.
- homeInfoParams is the right default — gets the bio visible without extra config

## The social icons option
- PaperMod supports [[params.socialIcons]] entries for LinkedIn, GitHub, etc.
- Skipped for now — need actual profile URLs first
- Format:
  ```toml
  [[params.socialIcons]]
    name = "linkedin"
    url = "https://linkedin.com/in/..."
  ```

## Result
- Homepage now shows bio + post list with clickable cards
- Menu: Posts, Tags, Archive all working
- Posts page lists all content/posts/ as clickable links with title, date, reading time, description
