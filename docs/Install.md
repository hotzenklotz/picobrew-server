# Installation

## 1) Server Installation
Download the project from Github either through git or download a [zip](https://github.com/hotzenklotz/picobrew-server/archive/master.zip).

Make sure you have Python (2.7) installed.

```
// Install Python requirements
pip install -r requirements.txt

// Start the server
sudo python server.py
```

The PicoBrew Server and UI will run under `http://localhost`(port 80).

## 2) Connect the PicoBrew machine
This is the tricky part. You have to fool the machine into believing the url `www.picobrew.com` belongs to your server. (DNS spoofing) There is several ways to do this:

- Connect the machine to your computer through an ad-hoc network and modify the `hosts` files.
- Some router allows you to configure your DNS settings accordingly:
    - Either you can specify a new DNS server (e.g. dnsmasq) that you can custom configure
    - or you can list a single domain and the IP address it should resolve too

### OSX

1. Start the PicoBrew server
2. Use the Internet Sharing feature of OSX. Either share your Wifi or Ethernet connection
3. Modify your `hosts` file under `etc/hosts` and add the following line to the end:
```
192.168.2.1    www.picobrew.com
```
The IP address must match the Mac's internet sharing bridge (check `ifconfig`)
4. Connect the PicoBrew machine through the above network interface.
5. If everything works correctly, you will see incoming requests logged to the terminal.
