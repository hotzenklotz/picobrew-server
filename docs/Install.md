# Installation

For a complete Raspberry Pi setup with Ethernet to the Zymatic, local DNS and
DHCP, automatic startup, and Wi-Fi internet access, see the
[getting started guide](Getting-Started.md).

## 1) Start the Server

Install [uv](https://docs.astral.sh/uv/) (includes `uvx`):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Run the `picobrew-server` command via `uvx` — no manual install or virtual environment needed:

```bash
# Linux / macOS — port 80 requires elevated privileges
sudo SECRET_KEY=your-secret-key uvx picobrew-server --data-dir ~/picobrew-data
```

The server binds to `0.0.0.0:80` by default so the PicoBrew machine can reach it without any custom port configuration. Use `--host`, `--port` and `--workers` to change this; pass other [gunicorn settings](https://gunicorn.org/reference/settings/) through the `GUNICORN_CMD_ARGS` environment variable.

`picobrew-server` runs gunicorn with the package's settings, including a compatibility patch: the machine ends HTTP header lines with a bare LF, which gunicorn's Python parser does not accept on its own, so every machine request would time out. To run gunicorn directly, pass `--config python:picobrew_server.gunicorn_config`.

Recipes (`recipes`), brew sessions (`sessions`) and machine registrations (`machines`) are stored in the data directory given by `--data-dir` or the `PICOBREW_DATA_DIR` environment variable. It defaults to the current working directory, so set it to keep your data in one place regardless of where you start the server.

Set `SECRET_KEY` to a fixed value to keep sessions stable across restarts. If omitted, a random key is generated each time.

## 2) Connect the PicoBrew Machine

Firmware 1.1.14 connects to `picobrew.com`; older traffic used `www.picobrew.com`. Redirect both hostnames to your server and ensure the machine uses the DNS resolver providing those overrides. See the [API reference](PicoBrew-API.md) for the firmware transport details. Several approaches work:

- **Existing ad blocker ([AdGuard Home](https://adguard.com/en/adguard-home/overview.html), [Pi-hole](https://pi-hole.net/))** — if your network already uses one as its DNS server, this is the simplest option: no router changes, and other devices are unaffected. See [Using AdGuard Home or Pi-hole](#using-adguard-home-or-pi-hole) below.
- **Router DNS override** — enter custom DNS entries for `picobrew.com` and `www.picobrew.com` pointing to your server's IP in your router admin panel.
- **dnsmasq** — run a local DNS server and add `address=/picobrew.com/<your-server-ip>` to your config; this domain rule covers the apex and its subdomains, including `www`.

Editing `/etc/hosts` only changes resolution on that computer. Internet Sharing alone does not establish that the PicoBrew's DNS queries will use those entries. Configure a DNS resolver reachable from the shared network and supply its address to the machine through DHCP or its network configuration.

### Using AdGuard Home or Pi-hole

If your network already sends DNS through [AdGuard Home](https://adguard.com/en/adguard-home/overview.html) (also available as a [Home Assistant add-on](https://github.com/hassio-addons/addon-adguard-home)) or [Pi-hole](https://pi-hole.net/), you can use it to answer `picobrew.com` with your server's address. This also helps when your router cannot hold local DNS records itself.

1. Give the computer running picobrew-server a fixed address, for example with a DHCP reservation in your router.
2. Add the overrides:
   - **AdGuard Home:** **Filters → DNS rewrites → Add DNS rewrite**. Add `picobrew.com` and `*.picobrew.com`, both pointing to your server's IP. The wildcard does not cover the bare domain, so you need both.
   - **Pi-hole:** **Local DNS → DNS Records** (in Pi-hole v6: **Settings → Local DNS Records**). Add `picobrew.com` and `www.picobrew.com`, both pointing to your server's IP. These records match exact names only.
3. Check that the resolver answers with your server's address:
   ```bash
   dig +short @<adguard-or-pihole-ip> picobrew.com
   dig +short @<adguard-or-pihole-ip> www.picobrew.com
   ```
4. Power-cycle the PicoBrew. In the resolver's query log, `picobrew.com` requests from the machine's IP should appear as rewritten or answered locally. The machine's requests then appear in the gunicorn access log.

If your router's DHCP hands out a second DNS server (for example `1.1.1.1`) next to the ad blocker, the machine could resolve the real `picobrew.com` through it. If the query log never shows the machine, remove the secondary DNS server from the router's DHCP settings.

### macOS (ad-hoc network)

1. Start the PicoBrew server (see above).
2. Enable Internet Sharing in **System Settings → General → Sharing → Internet Sharing**. Share your Wi-Fi or Ethernet connection over the bridge interface.
3. Find the bridge IP address:
   ```bash
   ifconfig bridge100
   ```
4. Configure a DNS resolver on the shared network to resolve both `picobrew.com` and `www.picobrew.com` to the actual bridge IP from step 3. Ensure DHCP supplies this resolver to the machine and that DNS queries can reach it.
5. Connect the PicoBrew machine to the shared network.
6. Incoming API requests will appear in the server's access log.
