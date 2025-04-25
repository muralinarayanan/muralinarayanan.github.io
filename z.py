from HTMLParser import HTMLParser
import sys

"""
ZScaler IP Page Parser

$ curl -sL http://ip.zscaler.com/cgi-bin/index.cgi | python zscaler-status.py
{"proxycloud": "zscalertwo.net",
"proxyhost":"zs2-*redacted*",
"ip": "*redacted_ip*"}
$ echo $?
0

$ echo "no valid content" | python zscaler-status.py
{"proxycloud":"None",
"proxyhost":"None",
"ip":"None"}
$ echo $?
2

# Not connected to a proxy but Internet is accessible
$ curl -sL http://ip.zscaler.com/cgi-bin/index.cgi | python zscaler-status.py
{"proxycloud":"None",
"proxyhost":"None",
"ip":"*redacted_ip*"}

# As a Nagios / Sensu check - pass -n flag
$ curl -Ls http://ip.zscaler.com/cgi-bin/index.cgi | python zscaler-status.py -n
OK - zScaler active |proxycloud:zscalertwo.net|proxyhost:zs2-*redacted*|ip:*redacted_ip*
$ echo $?
0
"""

class ZScalerPageParser(HTMLParser):
    """
    zScaler ip.zscaler.com/cgi-bin/index.cgi page parser class based upon overriding HTMLParser
    
    Note: the scrape is horrendous - font tags in 2015?
    """
    def __init__(self):
        HTMLParser.__init__(self)
        self.seen = {}
        self.parsestate = 'proxycloudsearch' # 
        self.proxycloud = None
        self.proxyhost = None
        self.ip = None

    def handle_starttag(self, tag, attrs):
        if tag == 'font':
            for name, val in attrs:
                if name == 'color' and val == 'green':
                    self.parsestate = 'proxycloudtag'
                if name == 'color' and val == 'black':
                    self.parsestate = 'proxyhosttag'
        elif tag == 'u':
            if self.parsestate == 'proxycloudtag':
                self.parsestate = 'proxyclouddata'
            elif self.parsestate == 'proxyhosttag':
                self.parsestate = 'proxyhostdata'
        elif tag == 'a':
            for name, val in attrs:
                if name == 'title' and val == 'MaxMind GeoIP':
                    self.parsestate = 'ipdata'

    def handle_endtag(self, tag):
        if tag == 'font':
            if self.parsestate == 'proxyclouddata':
                self.parsestate = 'proxyhostsearch'
            elif self.parsestate == 'proxyhostdata':
                self.parsestate = 'ipsearch'


    def handle_data(self, data):
        if self.parsestate == 'proxyclouddata':
            self.proxycloud = data
            self.parsestate = 'proxyhostsearch'
        elif self.parsestate == 'proxyhostdata':
            self.proxyhost = data
            self.parsestate = 'ipsearch'
        elif self.parsestate == 'ipdata':
            self.ip = data
            self.parsestate = 'done'


parser = ZScalerPageParser()
parser.feed(sys.stdin.read())
# I'm not going to load the json library or a templating lib for just 3 fields
if len (sys.argv) > 1 and sys.argv[1] == '-n':
    if parser.proxycloud is not None:
        print "OK - zScaler active |proxycloud:%s|proxyhost:%s|ip:%s" % (parser.proxycloud, parser.proxyhost, parser.ip)
    else:
        print "CRITICAL - zScaler inactive | proxycloud:%s|proxyhost:%s|ip%s" % (parser.proxycloud, parser.proxyhost, parser.ip)
else:
    print "{\"proxycloud\": \"%s\",\n\"proxyhost\":\"%s\",\n\"ip\": \"%s\"}" % (parser.proxycloud, parser.proxyhost, parser.ip)

if parser.proxycloud is not None:
    sys.exit(0)
    # Picard - "how can you be connected to zScaler but have no IP?!"
else:
    if parser.ip is None:
        sys.exit(2) # No IP, no zScaler - CRITICAL check status
    else:
        sys.exit(1) # IP, no zScaler - WARNING check status. Some might prefer to have only CRITICAL and OK status
