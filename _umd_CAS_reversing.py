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

# We'll begin by toying with logging into canvas.
# 1. A student clicks https://umd.instructure.com/
# 2. Redirect to https://umd.instructure.com/login
# 3. Redirect to https://umd.instructure.com/login/saml
# 4. Redirect to https://shib.idm.umd.edu/shibboleth-idp/profile/SAML2/Redirect/SSO?SAMLRequest=[...],
#    where the SAMLRequest parameter is randomly generated, in some form. I'm
#    sure it has significance in the SAML protocol, but the important part is
#    that it changes every time we request https://umd.instructure.com/.

canvas_request = requests.get("https://umd.instructure.com/login/saml", allow_redirects=False)
location = canvas_request.headers["location"]
SAML_request_header = location.split("SAMLRequest=")[1]

# Here are some examples of some SAML_request values.
# * fVLLbtswELz3KwTeKUqC5daEbcCNEcRA0hiWm0MuBUWuYwJ8qFwybf6%2BlNwi6cUAT8uZnQe5RGHNwDcpnt0BfibAWPy2xiGfLlYkBce9QI3cCQvIo%2BTd5uGeN2XFh%2BCjl96QD5TrDIEIIWrvSLHbrsgP1cxUPWtbuljMZ3RWnSRd1KqmbSv6%2BamHz%2FVckuIJAmbOiuQVmYiYYOcwChfzqGpqWjW0%2FnKsWl6P55kU25xDOxEn1jnGATljeNZ9qZUtk1UlqDQNem8gnqlWA8txTtoAG9027ABKB5CRdd0jKTb%2FjN94h8lC6CC8agnfD%2FfvAuNenY2FJGMKUEpvmfEv2rGxGVLs%2F%2Fb1VTul3cv1qvoLCPnd8bin%2B8fuSNbLcQ%2BfCgjrUTWL2jcwFt8zZUSzZB%2BBy8sbf8sSu%2B3eGy3filsfrIjXHYwTrehpgvJhfASM4GJuwxj%2F6yaAiLAiOS4Qtr5o%2Fv%2BV1p%2F%2BAA%3D%3D
# * fVLLbtswELz3KwTeKUqEG9uEbcCNUdRA2hiW20MvhSQuYwJ8qFwyaf6%2BlJwgycUAT8uZnQe5wtaaQWxTPLsj%2FE2AsfhnjUMxXaxJCk74FjUK11pAEXvRbL%2FfCV5WYgg%2B%2Bt4b8o5yndEiQojaO1Lsd2vyh8t5xW%2BWNVVquaSzbqbooqsXlCtZKTVXcz7rSfELAmbOmuQVmYiYYO8wti7mUcVrWnFaL07VZ1Hnc%2FObFLucQ7s2TqxzjAMKxvCsu1JLWyYrS5BpGnTeQDxTLQeW4yhtgI1uOTuC1AH6yJrmnhTbV%2BO33mGyEBoIj7qHn8e7N4Fxr87GQupjClD23jLjH7RjYzOkOLz09UU7qd3D9aq6CwjFt9PpQA%2F3zYlsVuMeMRUQNqNqFrXPYCy%2BZcoIvmLvgavLG%2F%2FIEvvdwRvdPxdffbBtvO5gnGhJ1QQVw%2FgIGMHF3IYx%2Fuk2QBthTXJcIGxz0fz4lTaf%2FgM%3D
# * fVLJbtswEL33KwTeKVryApWwDbgxihpIGsNye8gloKRxTICLyhmmzd%2BXkhMkufg6fG%2FeMlyisqaXm0hnd4A%2FEZCyf9Y4lOPDisXgpFeoUTplASW1st7c3coyn8g%2BePKtN%2BwD5TpDIUIg7R3LdtsVe5x35aktFhVfFA3w2XR64qpYKF5VzVeopgXMmynLfkPAxFmxtCIRESPsHJJylEaTsuCTkhfVcTKXxULOZg8s26Yc2ikaWWeiHqUQeNZNrjubR9vl0MVx0HgDdOa660WKc9IGxOC2FAfodICWRF3fs2zzZvzGO4wWQg3hWbfw63D7LjDs1clYiC3FAHnrrTD%2BSTsxNMOy%2FWtf37TrtHu6XlVzAaH8cTzu%2Bf6%2BPrL1ctgjxwLCelBNovYFjMX3TAlRLsVH4PJy459JYrfde6Pbl%2By7D1bRdQfDRHf8NEJlPxwBCRylNozxf28CKIIVS3GBifVF8%2FNXWn%2F5Dw%3D%3D
# * fVLLbtswELz3KwTeKUqy3dqEbcCNUdRAmhiWk0MvBUVuYgJ8qFyySf6%2BlJwgycXX5czOY7lEYU3PNyme3AH%2BJsBYPFvjkI8PK5KC416gRu6EBeRR8nbz65o3ZcX74KOX3pAPlMsMgQghau9IsduuyB817ybTCXR0UquOTuV0Thf1twUVTTeTM5BVV0tS3EPAzFmRvCITERPsHEbhYh5VTU2rhtbzYzXj9Vc%2Bm%2FwmxTbn0E7EkXWKsUfOGJ50V2ply2RVCSqNg84biCeqVc9ynAdtgA1uG3YApQPIyNr2lhSbN%2BNX3mGyEFoI%2F7SEu8P1u8CwV2djIcmYApTSW2b8o3ZsaIYU%2B9e%2BvmuntHu8XFV3BiH%2FeTzu6f62PZL1ctjDxwLCelDNovYFjMX3TBnRLNlH4PJ845sssdvuvdHypfjhgxXxsoNhohV9GKG8H46AEVzMbRjjn64CiAgrkuMCYeuz5uevtP7yHw%3D%3D

# Now we actually make the request, which would have happened automatically in
# the redirect had we not stopped it above (to get the intermediary SAMLRequest
# value, for testing).
# Importantly, the response we get from this includes a set-cookie header with
# a JSESSIONID that we need for later.
# Here's what this set-cookie header might look like:
# * Set-Cookie: JSESSIONID=A9F3E62D0EFA5BDBE0535C2AF7CEF46B.2; Path=/shibboleth-idp/; Secure; HttpOnly
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
