# picobrew-server

picobrew-server is a reverse-engineered replacement for the PicoBrew servers, for
use with the [PicoBrew Zymatic](http://www.picobrew.com/) homebrewing machine. Run
your own server, import BeerXML recipes and brew without a connection to
picobrew.com.

The server targets Zymatic firmware **1.1.14**. If your machine runs an older
version, follow the
[Zymatic firmware installation instructions](https://picobrew.com/Members/Software/Zymatic/Installation.cshtml)
to update it first. The server does not install firmware updates.

## Quick start

Install [uv](https://docs.astral.sh/uv/) and start the server on port 80:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo SECRET_KEY=your-secret-key uvx picobrew-server --data-dir ~/picobrew-data
```

Then point `picobrew.com` and `www.picobrew.com` at your server through DNS, so
the machine talks to it instead of the official servers.

- [Raspberry Pi guide](Getting-Started.md): a complete setup with the Pi wired to
  the Zymatic over Ethernet, local DNS and DHCP, and startup on boot.
- [Installation](Install.md): server options, data directory and other ways to
  redirect the machine's DNS.
- [FAQ](FAQ.md): recipes, machine programs and brew history.
- [HTTP API](PicoBrew-API.md): the Zymatic's protocol, from static analysis of
  firmware 1.1.14.

## Features

- Import BeerXML files and edit their machine programs
- Send your recipes and cleaning programs to the Zymatic
- Brew history with live temperature charts, stored in SQLite
- Session recovery and error reporting
- Local account and machine/sensor setup

!!! danger "Use at your own risk"

    This software sends temperature targets to your PicoBrew machine and will
    cause it to heat water. Any damage to your machine is at your own risk.

    If the Zymatic faults and the screen goes blank, don't leave it powered on.
    The circulating pump shuts off while the heater stays on, and a tube in the
    glycol loop may rupture.
