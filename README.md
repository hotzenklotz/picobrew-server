# picobrew-server
[![PyPI version](https://img.shields.io/pypi/v/picobrew_server)](https://pypi.org/project/picobrew_server/)
[![Python versions](https://img.shields.io/pypi/pyversions/picobrew_server)](https://pypi.org/project/picobrew_server/)
[![CI](https://img.shields.io/github/actions/workflow/status/hotzenklotz/picobrew-server/test_lint.yaml?branch=master)](https://github.com/hotzenklotz/picobrew-server/actions/workflows/test_lint.yaml)


This project reverse-engineers a server for the proprietary PicoBrew protocol for use with the [PicoBrew Zymatic](http://www.picobrew.com/), a homebrewing machine. It is intended to provide an alternative to run the machine without a connection to the official servers at picobrew.com. Run your own server and sync your recipes offline.

# HTTP API
The PicoBrew Zymatic's built-in Ardunio uses an unencrypted HTTP communication protocol. All request are `GET` requests and are not authenticated. The following documentation is based on Firmware 1.1.8.

- [PicoBrew Zymatic API Docs on Postman](https://documenter.getpostman.com/view/234053/Szf54VEX?version=latest)
- [PicoBrew Zymatic API Docs on GitHub](https://github.com/hotzenklotz/picobrew-server/wiki/PicoBrew-API)

# Installation

1. Install Python 3.10 or above
2. In a terminal download, install and run the project:
```bash
// Download and install
pip install picobrew_server

// Start the server in production mode on port 80

// Windows 
set FLASK_APP=picobrew_server
flask run --port 80 --host 0.0.0.0

// OSX / Linux
export FLASK_APP=picobrew_server 
flask run --port 80 --host 0.0.0.0
```

- Connect the PicoBrew machine to your computer and enable DNS spoofing. Re-route `www.picobrew.com` to your computer.
[More Details](https://github.com/hotzenklotz/picobrew-server/wiki/Install)

# Development 

1. Install Python 3.10+ & [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install all dependencies:

```bash
uv sync --group dev

# Start the server on http://localhost:5000
FLASK_APP=picobrew_server uv run flask run
```

3. Lint, Format, and Type Check changes:

```bash
uv run ruff check picobrew_server
uv run ruff format picobrew_server
uv run ty check picobrew_server
```


# Demo
You can try out the admin UI for uploading your XML files in this [online demo](https://picobrew.herokuapp.com). Please note, this website is for showcasing only and you should deploy your own version.


# Features
- Import BeerXML files
- Send all your recipes to the PicoBrew
- Send cleaning recipes to the PicoBrew
- Session Logging
- Session Recovery
- Admin Web UI

ToDo

- Session Charts

# Machine Support
- Picobrew Zymatic

ToDo
- Picobrew Z Series
- Picobrew Pico C

# Disclaimer
This software is provided "as is" and any expressed or implied warranties are disclaimed. This software submits recipes with temperature targets to your PicoBrew machine and will cause it to heat water. Any damage to your PicoBrew machine is at your own risk.

If the Zymatic faults and the screen goes blank, DON'T leave it powered on. The circulating pump will shut off and the heater stays on. A tube in the glycol loop may rupture.

# License

MIT @ Tom Herold
