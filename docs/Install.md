# Installation

## 1) Start the Server

Install [uv](https://docs.astral.sh/uv/) (includes `uvx`):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Run the server with gunicorn via `uvx` — no manual install or virtual environment needed:

```bash
# Linux / macOS — port 80 requires elevated privileges
sudo SECRET_KEY=your-secret-key uvx --with picobrew_server gunicorn --config gunicorn.conf.py
```

The server binds to `0.0.0.0:80` by default so the PicoBrew machine can reach it without any custom port configuration.

Set `SECRET_KEY` to a fixed value to keep sessions stable across restarts. If omitted, a random key is generated each time.

## 2) Connect the PicoBrew Machine

The machine connects to `www.picobrew.com` — you need to redirect that hostname to your server (DNS spoofing). Several approaches work:

- **Router DNS override** — enter a custom DNS entry for `www.picobrew.com` pointing to your server's IP in your router admin panel.
- **dnsmasq** — run a local DNS server and add `address=/www.picobrew.com/<your-server-ip>` to your config.
- **`/etc/hosts` via ad-hoc network** — share your network connection from your computer, then add `www.picobrew.com` to `/etc/hosts`.

### macOS (ad-hoc network)

1. Start the PicoBrew server (see above).
2. Enable Internet Sharing in **System Settings → General → Sharing → Internet Sharing**. Share your Wi-Fi or Ethernet connection over the bridge interface.
3. Find the bridge IP address:
   ```bash
   ifconfig bridge100
   ```
4. Add this line to `/etc/hosts`:
   ```
   192.168.2.1    www.picobrew.com
   ```
   Replace `192.168.2.1` with the actual bridge IP from step 3.
5. Connect the PicoBrew machine to the shared network.
6. Incoming API requests will appear in the gunicorn access log.
