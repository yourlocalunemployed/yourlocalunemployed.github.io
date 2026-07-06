# Blog backup

Layered backup for this blog. The three copies:

1. **Working copy** — the live repo on the VM.
2. **GitHub** — `git push` sends full committed history offsite (versioned).
3. **Local snapshots** — `backup-blog.sh` writes a self-contained `.tar.gz`
   (source + `.git` history + any uncommitted/untracked work) to every
   off-VM target that's available:
   - `~/OneDrive/blog-backups/` — offsite via OneDrive sync
   - `/mnt/hgfs/ClaudeDIrecotryVM/blog-backups/` — the VMware host disk

`public/` (regenerable build output) is excluded to keep archives lean.
The newest 7 archives are kept per target (`BLOG_BACKUP_RETAIN` to change).

## Run a backup now

```bash
~/blog/scripts/backup-blog.sh
```

Log: `~/.local/state/blog-backup/backup.log`

## Automatic daily backup

A systemd **user** timer runs it once a day (`Persistent=true`, so a run
missed while the VM was off fires at the next login). Install/reinstall:

```bash
cp scripts/systemd/blog-backup.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now blog-backup.timer
systemctl --user list-timers blog-backup.timer   # check schedule
```

Because it's a *user* timer, it fires during login sessions. To have it run
even when logged out, enable lingering once (needs root):

```bash
sudo loginctl enable-linger student
```

## Restore

```bash
tar -xzf blog-<timestamp>.tar.gz -C /some/dir
cd /some/dir/blog
hugo --minify        # regenerate public/
```

The extracted `.git` is a full clone — `git log`, `git checkout`, etc. all work
offline, independent of GitHub.
