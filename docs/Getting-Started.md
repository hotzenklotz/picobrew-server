# Getting started on a Raspberry Pi

This guide runs picobrew-server on a Raspberry Pi connected directly to a
**PicoBrew Zymatic over Ethernet**. The Pi stays connected to your home Wi-Fi for
SSH access, software downloads and Raspberry Pi OS updates.

```text
Internet / home router
        |
      Wi-Fi
        |
  Raspberry Pi
  wlan0: home network address, internet access
  eth0:  192.168.50.1, PicoBrew HTTP server + DNS + DHCP
        |
   Ethernet cable
        |
  PicoBrew Zymatic
  192.168.50.100–192.168.50.150 (assigned by the Pi)
```

The machine asks the Pi to resolve `picobrew.com` or `www.picobrew.com`. The Pi
answers with `192.168.50.1`, so the machine's normal HTTP requests reach the local
server on port 80. DHCP supplies the machine's address and DNS settings.

The two networks use separate subnets. Wi-Fi provides the Pi's default route;
Ethernet only provides a route to the machine. This setup does not require a
bridge, Internet Sharing or NAT. The machine uses the local server and does not
need internet access.

## 1. Prepare the Pi and connect Wi-Fi

You need:

- A Raspberry Pi with Wi-Fi and Ethernet, such as a Pi 3, 4 or 5; a USB Ethernet
  adapter also works if your Pi has no Ethernet port.
- A microSD card, suitable Pi power supply and a normal Ethernet cable.
- A PicoBrew Zymatic and your home Wi-Fi credentials.
- Another computer to prepare the card and access the Pi's web interface.

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to install
**Raspberry Pi OS Lite (64-bit)** on a compatible Pi. This guide targets
**Raspberry Pi OS Bookworm or later with NetworkManager** and Python 3.10 or
later. Older systems using `dhcpcd` need different network configuration.

In Imager's OS customisation settings, choose a hostname (for example
`picobrew-pi`), create your username and password, configure your home Wi-Fi and
Wi-Fi country, and enable SSH. There is no assumption that your username is
`pi`.

Boot the Pi and connect from your computer:

```bash
ssh YOUR_USERNAME@picobrew-pi.local
```

Replace `YOUR_USERNAME` with the username you created. If `.local` discovery
does not work, find the Pi's Wi-Fi IP address in your router's client list and
use that address instead. Run the remaining shell commands **on the Pi**, as
that regular user, using `sudo` where shown.

Check networking:

```bash
nmcli device status
ip -4 route
```

Wi-Fi should show as connected, with a default route through its interface. If
you did not configure Wi-Fi in Imager, connect interactively:

```bash
sudo nmcli --ask device wifi connect 'YOUR_WIFI_SSID'
```

See the [official Raspberry Pi networking documentation](https://www.raspberrypi.com/documentation/computers/configuration.html#networking)
for Wi-Fi configuration and country settings.

Update the OS and install the tools used below:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y git curl python3 python3-venv dnsmasq dnsutils tcpdump
sudo systemctl stop dnsmasq
```

Reboot if the OS update requires it, then reconnect over Wi-Fi.

## 2. Install picobrew-server

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) as your
regular user:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new SSH session so the installer's PATH change takes effect, then:

```bash
uv --version
git clone https://github.com/hotzenklotz/picobrew-server.git "$HOME/picobrew-server"
cd "$HOME/picobrew-server"
uv venv --python python3
uv pip install .
mkdir -p recipes sessions machines
```

This installs the application, Uvicorn and the Flask-to-ASGI adapter in a
persistent `.venv`, following uv's
[virtual environment workflow](https://docs.astral.sh/uv/pip/environments/).

Recipes, brew session logs and machine registrations are stored relative to the
server's working directory. In this guide that directory is
`$HOME/picobrew-server`, so your data lives in its `recipes`, `sessions` and
`machines` directories.

## 3. Start the server automatically

Create a persistent secret key once. The environment file is readable only by
root; systemd reads it for the service:

```bash
sudo install -m 600 /dev/null /etc/picobrew-server.env
python3 -c 'import secrets; print("SECRET_KEY=" + secrets.token_hex(32))' \
  | sudo tee /etc/picobrew-server.env >/dev/null
```

Create the service from the same regular-user SSH session. The unquoted `EOF`
lets the shell insert your actual username and home directory into the file:

```bash
PI_USER="$(id -un)"
sudo tee /etc/systemd/system/picobrew-server.service >/dev/null <<EOF
[Unit]
Description=PicoBrew local server
After=network.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=${HOME}/picobrew-server
EnvironmentFile=/etc/picobrew-server.env
ExecStart=${HOME}/picobrew-server/.venv/bin/uvicorn picobrew_server.asgi:create_app --factory --host 0.0.0.0 --port 80 --workers 2
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now picobrew-server
sudo systemctl status picobrew-server --no-pager
curl -I http://127.0.0.1/
```

The response should be HTTP `200 OK`. The service runs as your regular user;
`CAP_NET_BIND_SERVICE` allows it to listen on port 80. The Uvicorn command
binds to `0.0.0.0:80`, so both Ethernet and Wi-Fi can reach it. The worker count
is limited to two for the Pi. See the
[systemd execution reference](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)
for capability settings and the [Uvicorn settings reference](https://www.uvicorn.org/settings/)
for server options.

Find the Pi's Wi-Fi address:

```bash
ip -4 address show wlan0
```

On your computer, open `http://PI_WIFI_IP/`, replacing `PI_WIFI_IP` with that
address. You can also try `http://picobrew-pi.local/` if hostname discovery works.
Use **HTTP**, since this setup does not configure HTTPS.

## 4. Connect the machine and configure Ethernet

Plug an Ethernet cable directly from the Pi's Ethernet port into the Zymatic's
Ethernet port and turn on the machine so the Ethernet link is active. Keep your
SSH session connected through Wi-Fi. The machine will receive its network
settings after DHCP is configured in the next step.

Keep this cable on the private Pi-to-machine link. An isolated switch is also
possible, but do not connect that switch to your home router: the Pi will serve
DHCP on this Ethernet network.

Check interface names and existing connection profiles:

```bash
nmcli device status
nmcli -f NAME,TYPE,DEVICE connection show
ip -4 route
```

The examples use `eth0` for Ethernet and `wlan0` for Wi-Fi. If a USB adapter or
your OS uses other names, substitute them throughout, including in the dnsmasq
configuration below.

Check that **`192.168.50.0/24` does not overlap your home Wi-Fi network or a VPN
route**. If it does, choose another unused private subnet and replace every
`192.168.50.*` address in this guide consistently.

Create a persistent Ethernet profile:

```bash
sudo nmcli connection add type ethernet ifname eth0 con-name picobrew-ethernet \
  ipv4.method manual ipv4.addresses 192.168.50.1/24 \
  ipv4.never-default yes ipv4.ignore-auto-dns yes \
  ipv6.method disabled \
  connection.autoconnect yes connection.autoconnect-priority 100

sudo nmcli connection up picobrew-ethernet
ip -4 address show eth0
ip -4 route
```

Expect `192.168.50.1/24` on Ethernet, a route to `192.168.50.0/24` through
`eth0`, and your default route still through `wlan0`. There is no gateway or DNS
server configured on the Pi's Ethernet profile. `ipv4.never-default` keeps this
connection from becoming the Pi's internet route; the higher autoconnect
priority prefers this profile over a default wired profile on reboot. These
settings are documented in the [NetworkManager reference](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html).

Run `connection add` only once. To change an existing profile, use
`sudo nmcli connection modify picobrew-ethernet ...` and then bring it up again.
If another wired profile has a higher autoconnect priority, disable autoconnect
for that profile using its name from the listing above:

```bash
sudo nmcli connection modify 'OTHER_WIRED_PROFILE' connection.autoconnect no
```

## 5. Configure DNS spoofing and DHCP

Here, DNS spoofing means serving local DNS overrides to the machine. Editing
the Pi's `/etc/hosts` alone does not configure the machine's DNS resolver.

Create a dnsmasq configuration for the Ethernet link:

```bash
sudo tee /etc/dnsmasq.d/picobrew.conf >/dev/null <<'EOF'
# Serve the private Ethernet link only, including when it appears after boot.
interface=eth0
except-interface=lo
bind-dynamic

# This resolver serves local names only; the Pi keeps its Wi-Fi DNS settings.
no-resolv
no-hosts
address=/picobrew.com/192.168.50.1
local=/picobrew.com/

# Give the machine an address and tell it to use the Pi for DNS.
dhcp-range=192.168.50.100,192.168.50.150,255.255.255.0,12h
dhcp-option=option:dns-server,192.168.50.1
dhcp-option=option:router,192.168.50.1
dhcp-authoritative
log-dhcp
EOF

sudo dnsmasq --test
sudo systemctl enable --now dnsmasq
sudo systemctl restart dnsmasq
sudo systemctl status dnsmasq --no-pager
```

The domain rule covers both `picobrew.com` and its subdomains, including `www`.
`local` prevents forwarding other query types for that domain. `bind-dynamic`
handles the Ethernet interface acquiring its address after dnsmasq starts.
See the [dnsmasq manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html)
for the DNS and DHCP options.

The advertised gateway is the Pi, but this guide does not enable internet
forwarding for the machine. Its API destination is on the same Ethernet subnet.
The Pi's own internet access continues through Wi-Fi and the DNS servers supplied
by your home router. Do not change the Pi's Wi-Fi DNS server to `192.168.50.1`:
this dnsmasq instance has no upstream DNS server.

On an existing Pi, check `/etc/dnsmasq.conf` and other files in
`/etc/dnsmasq.d/` for conflicting settings. This guide assumes a fresh install
without another DHCP or DNS service on the Ethernet interface.

## 6. Verify DNS, internet access and machine requests

From the Pi, check both overridden names:

```bash
dig @192.168.50.1 picobrew.com A +short
dig @192.168.50.1 www.picobrew.com A +short
```

Both should return `192.168.50.1`. Check the server using the machine's Ethernet
recipe-sync route and hostname:

```bash
curl --noproxy '*' --resolve picobrew.com:80:192.168.50.1 \
  'http://picobrew.com/API/SyncUSer?user=00000000000000000000000000000000&machine=setup-test'
```

This should return a `#`-framed list of cleaning programs. `--resolve` checks
HTTP directly; the separate `dig` commands check DNS. The route spelling comes
from the [firmware API reference](PicoBrew-API.md).

Confirm that the Pi can still resolve internet names and reach its package
repositories over Wi-Fi:

```bash
ip -4 route get 1.1.1.1
getent ahostsv4 archive.raspberrypi.com
sudo apt update
```

The route lookup should use `wlan0`; name resolution and the update should
succeed.

Use the machine's wired/Ethernet connection mode if its setup offers a choice,
and use automatic addressing (DHCP). Restart the machine after the Pi's DHCP
server is running so it requests fresh network settings. If manual network
settings are required, use an unused address such as `192.168.50.10`, netmask
`255.255.255.0`, gateway `192.168.50.1` and DNS server `192.168.50.1`.

Check for a lease and watch requests while the machine connects or syncs:

```bash
sudo cat /var/lib/misc/dnsmasq.leases
sudo journalctl -u dnsmasq -n 50 --no-pager
sudo journalctl -u picobrew-server -f
```

Expect a lease in `192.168.50.100–150` and requests to `/API/...` in the server's
access log. Press Ctrl+C to stop following the log; the service keeps running.
When prompted to select an account, choose **PicoBrew Server**. Upload BeerXML
recipes through the web interface; recipes need a PicoBrew mashing program to
appear on the machine. See the [FAQ](FAQ.md) for recipe requirements.

Once everything works, reboot the Pi and repeat the DNS, HTTP and internet
checks. Both services and the Ethernet profile should start automatically.
Restart the machine if it needs to renew its lease.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Ethernet profile cannot activate | Confirm the machine is on, the cable has link, and the interface name matches `nmcli device status`. |
| No DHCP lease | Check the machine uses Ethernet and DHCP, then restart it. Look for DHCP activity with `sudo tcpdump -ni eth0 'udp port 67 or udp port 68'`. A manually configured machine will not have a lease. |
| `dig` times out or returns another address | Check `ip -4 address show eth0`, `sudo dnsmasq --test` and `sudo journalctl -u dnsmasq -n 50 --no-pager`. Verify that the service reads `/etc/dnsmasq.d/` and no other configuration overrides the rule. |
| DNS works on the Pi, but the machine never connects | Verify the machine's DNS is `192.168.50.1`. Watch its traffic with `sudo tcpdump -ni eth0 'port 53 or tcp port 80'`. The Pi-side checks alone do not prove the machine received the DNS setting. |
| Server fails to start | Read `sudo journalctl -u picobrew-server -n 50 --no-pager`; check the username, paths, `.venv` and environment file in the unit. Run `sudo ss -ltnp 'sport = :80'` to check for another web server. |
| dnsmasq reports an address already in use | Check `sudo ss -lntup` for an existing DNS service on port 53 or DHCP service on UDP 67. Resolve conflicting listeners or configuration before restarting dnsmasq. |
| Pi loses internet access | Check for overlapping subnets and a default route through Ethernet. Verify `ipv4.never-default` is `yes` on `picobrew-ethernet`, Wi-Fi is connected and its DNS still comes from the home network. |
| A firewall blocks the machine | Allow inbound TCP 80, TCP/UDP 53 and UDP 67 on the Ethernet interface. If accessing the web UI over Wi-Fi, allow TCP 80 from your home network too. |

## Updates and backups

Pi OS updates continue to use Wi-Fi:

```bash
sudo apt update
sudo apt full-upgrade -y
```

Before updating the application, finish any active brew and back up your data:

```bash
tar -C "$HOME/picobrew-server" \
  -czf "$HOME/picobrew-backup-$(date +%F).tar.gz" recipes sessions machines
```

Also retain `/etc/picobrew-server.env`,
`/etc/systemd/system/picobrew-server.service` and
`/etc/dnsmasq.d/picobrew.conf` when backing up the Pi's configuration.

If your existing service uses Gunicorn, first update its `ExecStart` to the
Uvicorn command in section 3 and run `sudo systemctl daemon-reload`.

For an unmodified checkout, update the application with:

```bash
cd "$HOME/picobrew-server"
git pull --ff-only
sudo systemctl stop picobrew-server
uv pip install --upgrade .
sudo systemctl start picobrew-server
sudo systemctl status picobrew-server --no-pager
```

If installation fails, check its error before restarting; do not proceed with a
brew until the HTTP and machine connection checks pass again. Keep the data
directories and persistent secret key across updates.
