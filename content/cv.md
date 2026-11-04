---
title: "CV"
layout: cv
description: "Billal Rehmani — IT student specialising in networking and cybersecurity, Australia. Five TAFE qualifications, a self-built home lab, and the write-ups to show for it."
ShowToc: false
hideMeta: true
comments: false
# Content below follows Bill's resume (2026 edition), transcribed on 2026-10-24.
# Deliberately left off this public page: phone number, email addresses, the
# references section and their contact details. Nothing here is inferred.
# Added 2026-11-04 at Bill's request: the TAFE capstone (`capstone` below),
# its skills folded into `skills`, and "Team leadership" in `strengths`. Every
# line of that comes from the project's own write-up at content/tafe-soc/,
# not from the resume.
name: "Billal Rehmani"
headline: "IT student · networking & cybersecurity"
location: "Australia"
summary: >-
  IT student specialising in networking and cybersecurity, with five TAFE qualifications and
  a self-built home lab I use to turn coursework into working systems. I design, deploy and
  troubleshoot production-style infrastructure — firewalls, identity, monitoring, and
  intrusion detection — and document each build on this blog. Comfortable working
  methodically through complex, multi-layered problems, and fluent with modern AI-assisted
  development tools. Currently seeking an entry-level networking, security, or IT support
  role where I can apply this hands-on experience and keep growing.
education:
  - when: "Feb 2026 – Dec 2026 · current"
    what: "Diploma — Cybersecurity & Networking"
    where: "TAFE NSW"
    note: "Capstone: team lead for a group of five, designing, building and then attacking and defending a nine-zone SOC network on Proxmox. Details under Capstone project, above."
  - when: "completed Dec 2023"
    what: "Diploma — Advanced Networking & Cloud Architecture"
    where: "TAFE NSW"
  - when: "completed Dec 2022"
    what: "Certificate IV — Networking"
    where: "TAFE NSW"
  - when: "completed Jun 2022"
    what: "Certificate IV — Cyber Security"
    where: "TAFE NSW"
  - when: "completed Jun 2021"
    what: "Certificate IV — Information Technology"
    where: "TAFE NSW"
certifications:
  - "CCNA — Introduction to Networking"
  - "CCNA — Routing & Switching"
  - "Cisco — Computer Hardware Basics"
  - "AWS Cloud Foundations"
skills:
  - "pfSense firewalls & VLAN segmentation"
  - "Identity & SSO (Authentik, LDAP, OIDC)"
  - "SIEM & log analysis (Loki, Grafana, Wazuh)"
  - "IDS/IPS (Suricata)"
  - "Monitoring (Prometheus, Alertmanager)"
  - "Docker & container services"
  - "VPN & remote access (WireGuard, Tailscale, OpenVPN)"
  - "RADIUS & Active Directory (FreeRADIUS)"
  - "Linux (Debian, Kali)"
  - "Virtualisation (VMware, Proxmox)"
  - "Bash scripting & automation"
  - "AI-assisted workflows"
strengths:
  - "Team leadership"
  - "Self-directed & fast learner"
  - "Methodical troubleshooting"
  - "Clear technical writing"
  - "Adaptable under pressure"
# The TAFE capstone, from the project's write-up (content/tafe-soc/index.md).
capstone:
  when: "2026 · final term"
  title: "TAFE SOC network group project"
  where: "Diploma — Cybersecurity & Networking · TAFE NSW · CL5 \"Build and Battle\""
  role: "Team lead in a group of five: coordinated the planning, built the core infrastructure, and ran blue-team detection across the live exercise."
  url: "/tafe-soc/"
  bullets:
    - "Designed a nine-zone network on Proxmox: pfSense as router-on-a-stick over seven 802.1Q VLANs, alias-based deny rules, and Red-to-Blue traffic denied both ways and logged."
    - "Built OpenVPN remote access with FreeRADIUS against Active Directory, where RADIUS group membership decides what a client can reach; proven live with an accepted member and a rejected non-member."
    - "Ran Suricata IDS on three segments, correlated against Wazuh, across four fixed-role attack-and-defence rounds, from reconnaissance to blocking-mode validation."
    - "Found and documented a real detection gap: the generic ruleset missed a boolean-based SQL injection, caught only in the database's query log, and the incident-response steps went into the blue-team playbook."
    - "Measured disaster recovery instead of estimating it: vzdump backups, an off-host copy and a timed restore, about 2 min 10 sec RTO against a 1-hour target."
    - "Troubleshot with evidence: a campus WAN outage isolated by packet capture, a RADIUS LDAP bind chain, a broken log pipeline, and domain-controller clock drift breaking Kerberos."
  skills:
    - "Network segmentation & VLAN design"
    - "pfSense firewall policy"
    - "IDS/IPS (Suricata)"
    - "SIEM correlation (Wazuh)"
    - "RADIUS & AAA via Active Directory"
    - "OpenVPN remote access"
    - "Incident response"
    - "Red / blue team exercises"
    - "Backup & DR testing"
    - "Proxmox virtualisation"
    - "Team leadership"

# Home lab projects, in the resume's own groupings and words. Each links to
# the write-up on this blog where it was built.
projects:
  - title: "Segmented network & firewall"
    stack: "pfSense, VLANs"
    post: "/posts/vlan-segmentation-pfsense/"
    bullets:
      - "Designed an isolated lab network behind pfSense with separate trusted, IoT and guest VLANs, enforcing traffic rules between segments."
      - "Built and verified network isolation so the lab cannot reach the home network — validated with packet captures and firewall logs."
  - title: "Self-hosted identity & secrets"
    stack: "Authentik, Vaultwarden, Caddy"
    post: "/posts/identity-provider-authentik-grafana-sso/"
    bullets:
      - "Deployed single sign-on with Authentik, integrating firewall and dashboard logins via LDAP and OIDC."
      - "Ran a reverse proxy (Caddy) issuing automatic wildcard TLS certificates, and a self-hosted password vault, kept off the public internet."
  - title: "Monitoring, alerting & SIEM"
    stack: "Prometheus, Grafana, Loki"
    post: "/posts/homelab-siem-loki/"
    bullets:
      - "Built a metrics stack (Prometheus, Grafana, Alertmanager) with push notifications to a phone for outages and disk pressure."
      - "Centralised firewall and server logs into a Loki SIEM, writing parsing pipelines and a live SSH brute-force detection rule that alerts on threshold breach."
  - title: "Vulnerability scanning & remote access"
    stack: "OpenVAS, Tailscale"
    post: "/posts/two-vpns-one-phone-tailscale/"
    bullets:
      - "Ran authenticated OpenVAS/Greenbone scans against the lab and used the findings to close real security gaps."
      - "Consolidated remote access onto a hardened Tailscale mesh — subnet routing, split DNS, and least-privilege access rules — keeping a self-hosted WireGuard tunnel as independent backup."
  - title: "Encrypted backups & automation"
    stack: "Bash, age, n8n"
    post: "/posts/backup-you-havent-restored/"
    bullets:
      - "Scripted encrypted, off-box nightly backups with restore testing, and automated verification workflows."
experience:
  - when: "Mar 2025 – Aug 2025"
    what: "Warehouse Assistant"
    where: "Choice Plastics"
    bullets:
      - "Shaped and finished polycarbonate sheets — rounding, bending and moulding to spec."
      - "Maintained a clean, safe working environment in line with workplace standards."
      - "Prepared finished materials for dispatch, ensuring quality before shipping."
  - when: "Apr 2020 – Dec 2021"
    what: "Warehouse Assistant"
    where: "YIPOSE Trading Company"
    bullets:
      - "Processed and fulfilled customer orders in Shopify, maintaining accurate invoice and label records."
      - "Collaborated with the product design team using Adobe Photoshop for label and packaging assets."
      - "Inspected incoming shipments for accuracy and routed stock to the correct departments."
      - "Conducted stock counts and maintained inventory control per company procedures."
---
