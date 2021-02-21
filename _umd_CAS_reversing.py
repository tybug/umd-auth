from pathlib import Path
import urllib
import json

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from config import USERNAME, PASSWORD


# Detailed Trace of a Shibboleth Login:
# https://docs.shib.ncsu.edu/docs/shiblogindetails.html

canvas_request = requests.get("https://umd.instructure.com/login/saml", allow_redirects=False)
location = canvas_request.headers["location"]
SAML_request_header = location.split("SAMLRequest=")[1]

# Importantly, the response we get from this includes a set-cookie header with
# a JSESSIONID that we need for later.
sso_request = requests.get(f"https://shib.idm.umd.edu/shibboleth-idp/profile/SAML2/Redirect/SSO?SAMLRequest={SAML_request_header}")
# The jsession id cookie is actually set in the first request, then we're
# redirected to [...]/Redirect/SSO?execution=e1s1.
jsession_id = sso_request.history[0].cookies["JSESSIONID"]

cookies = {"JSESSIONID": jsession_id}
data = {"j_username": USERNAME, "j_password": PASSWORD, "_eventId_proceed": ""}
r = requests.post("https://shib.idm.umd.edu/shibboleth-idp/profile/SAML2/Redirect/SSO?execution=e1s1", data=data, cookies=cookies)
# sanity check to ensure our request / jsession id was accepted
assert "Please complete your multi-factor authentication using Duo." in r.text

# r.url is "https://shib.idm.umd.edu/shibboleth-idp/profile/SAML2/Redirect/SSO?execution=e1s2"
umd_sso_url = r.url

# There's an iframe on this page (the duo mobile 2fa element) which makes some
# requests for us. We need to get the source code of that iframe in order to
# replicate the requests by hand. Duo has a js library that sets the iframe
# source based on some parameters in the source code of this page, so we
# replicate that js code here to create the iframe url and retrieve its source.
#
# The duo js code is minified on the umd page, but an unmified version (that
# seems to be accurate as far as I can tell) can be found here:
# http://shibboleth.net/pipermail/commits/2017-September/031081.html.
soup = BeautifulSoup(r.text, features="lxml")
duo_iframe = soup.find(id="duo_iframe")
duo_host = duo_iframe.get("data-host")
duo_sig_request = duo_iframe.get("data-sig-request")

duo_sig = duo_sig_request.split(":")[0]
app_sig = duo_sig_request.split(":")[1]


# Apparently javascript's encodeURIComponent function (which we are replicating
# here) replaces "/" as well, so we pass `safe=""`` to emulate this.
current_url_encoded = urllib.parse.quote(umd_sso_url, safe="")

duo_iframe_source_url = f"https://{duo_host}/frame/web/v1/auth?tx={duo_sig}&parent={current_url_encoded}&v=2.6"
duo_iframe_source = requests.get(duo_iframe_source_url)

options = Options()
options.headless = True
driver = webdriver.Chrome(Path(__file__).parent / "chromedriver", options=options)
driver.get(duo_iframe_source_url)
sid = driver.current_url.split("sid=")[1]
sid = urllib.parse.unquote(sid)

data = {
    "sid": sid,
    "device": "phone1",
    "factor": "Passcode",
    "passcode": "495887343", # XXX: MUST use a valid (unused) passcode here
    "out_of_date": "False",
    "days_out_of_date": "0",
    "days_to_block": "None"
}
r = requests.post(f"https://{duo_host}/frame/prompt", data=data)
txid = json.loads(r.content)["response"]["txid"]

data = {"sid": sid, "txid": txid}
r = requests.post(f"https://{duo_host}/frame/status", data=data)

data = {"sid": sid}
r = requests.post(f"https://{duo_host}/frame/status/{txid}", data=data)
auth_sig = json.loads(r.content)["response"]["cookie"]

sig_response = f"{auth_sig}:{app_sig}"
data = {"_eventId": "proceed", "sig_response": sig_response}
r = requests.post(umd_sso_url, data=data, cookies=cookies)
shib_idp_session = r.headers["set-cookie"].split("shib_idp_session=")[1]


# With these two cookies, we are basically god. We can make a request to any
# umd website with full authentication permissions.
cookies = {
    "JSESSIONID": jsession_id,
    "shib_idp_session": shib_idp_session
}

# Interestingly, websites under umd control seem to have a hierarchy.
# If you use CAS to log into a website of tier X, you can then freely access
# any website in a tier >=X, but the opposite is not true.
# To take advantage of this, we should log into the highest tier website we can,
# so the session applies to any other site we care to access as well.
#
# Tier 1
# ------
# * https://identity.umd.edu/mfaprofile
#
# Tier 2
# ------
# * http://umd.instructure.com/
# * https://return.umd.edu/covid/returnstatus
