"""
Python Website Blocker — block sites via the system hosts file.
User input, URL pattern recognition, and optional page scraping.
"""

import platform
import re

import requests
import streamlit as st
from bs4 import BeautifulSoup

def get_hosts_path():
    if platform.system() == "Windows":
        return r"C:\Windows\System32\drivers\etc\hosts"
    return "/etc/hosts"


REDIRECT = "127.0.0.1"
HOSTS_PATH = get_hosts_path()

DISTRACTION_KEYWORDS = (
    "game",
    "casino",
    "dating",
    "meme",
    "shopping",
    "sale",
    "stream",
    "watch",
    "social",
)

DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def clean_url(url):
    url = url.strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.split("/")[0].split("?")[0]
    if "." not in url:
        return None
    if not DOMAIN_RE.match(url):
        return None
    return url


def domain_matches_pattern(domain, pattern):
    pattern = pattern.strip().lower()
    domain = domain.lower()
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return domain.endswith(suffix) or domain == pattern[2:]
    return domain == pattern or pattern in domain


def block_website(website):
    clean_site = clean_url(website)
    if clean_site is None:
        return False, "Enter full domain (e.g. geeksforgeeks.org)"

    try:
        with open(HOSTS_PATH, "r+", encoding="utf-8") as file:
            content = file.read()
            if f"{REDIRECT} {clean_site}" in content:
                return False, "Already blocked!"
            file.write(f"\n{REDIRECT} {clean_site}\n")
            file.write(f"{REDIRECT} www.{clean_site}\n")
        return True, f"Blocked {clean_site}"
    except PermissionError:
        return False, "Run terminal as Administrator (Windows) or use sudo"
    except OSError as err:
        return False, str(err)


def unblock_website(website):
    clean_site = clean_url(website)
    if clean_site is None:
        return False, "Enter full domain (e.g. geeksforgeeks.org)"

    try:
        with open(HOSTS_PATH, "r", encoding="utf-8") as file:
            lines = file.readlines()
        with open(HOSTS_PATH, "w", encoding="utf-8") as file:
            for line in lines:
                if clean_site not in line:
                    file.write(line)
        return True, f"Unblocked {clean_site}"
    except PermissionError:
        return False, "Run terminal as Administrator (Windows) or use sudo"
    except OSError as err:
        return False, str(err)


def hosts_file_writable():
    try:
        with open(HOSTS_PATH, "a", encoding="utf-8"):
            pass
        return True
    except PermissionError:
        return False
    except OSError:
        return False


def show_result(ok, msg):
    if ok:
        st.success(msg)
    else:
        st.error(msg)


def get_blocked_sites():
    blocked = []
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8") as file:
            for line in file:
                if line.startswith(REDIRECT) and "www." not in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        site = parts[1]
                        if site != "localhost" and site not in blocked:
                            blocked.append(site)
    except OSError:
        pass
    return blocked


def scrape_page(user_input):
    domain = clean_url(user_input)
    if domain:
        url = f"https://{domain}"
    elif user_input.strip().lower().startswith(("http://", "https://")):
        url = user_input.strip()
        domain = clean_url(url) or url
    else:
        return {"ok": False, "error": "Invalid URL or domain"}

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WebsiteBlocker/1.0)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    soup = BeautifulSoup(response.text, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    body = soup.get_text(" ", strip=True)[:2500]
    combined = f"{title} {body}".lower()
    hits = [kw for kw in DISTRACTION_KEYWORDS if kw in combined]

    block_domain = clean_url(url) or domain
    return {
        "ok": True,
        "domain": block_domain,
        "title": title or "(no title)",
        "keyword_hits": hits,
        "suggest_block": len(hits) >= 1,
    }


st.title("Python Website Blocker")
st.caption("Hosts file blocker — bulk, patterns, page scan")

if not hosts_file_writable():
    st.error(
        "**Cannot edit the hosts file.** Close Streamlit, open **PowerShell as Administrator**, "
        "then run: `cd W:\\Yugandhar_WNS_Projects\\Python_Website_Blocker` and `streamlit run app.py`"
    )

tab_block, tab_list, tab_scan = st.tabs(["Block sites", "Blocked list", "Scan website"])

with tab_block:
    st.header("Block or unblock")
    website = st.text_input("Website", placeholder="geeksforgeeks.org or https://www.facebook.com")
    st.caption("Include .com / .org etc. Admin rights needed to change hosts file.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Block", type="primary", use_container_width=True):
            if website:
                ok, msg = block_website(website)
                show_result(ok, msg)
    with c2:
        if st.button("Unblock", use_container_width=True):
            if website:
                ok, msg = unblock_website(website)
                show_result(ok, msg)

    st.divider()
    st.subheader("Bulk block (one site per line)")
    bulk = st.text_area("Websites", placeholder="facebook.com\ntwitter.com")
    if st.button("Block all"):
        if bulk:
            count = 0
            for line in bulk.strip().splitlines():
                if line.strip():
                    ok, _ = block_website(line.strip())
                    if ok:
                        count += 1
            st.success(f"Blocked {count} site(s)")

    st.divider()
    st.subheader("Block domains matching a pattern")
    pattern = st.text_input(
        "Pattern",
        placeholder="facebook or *.org or shop",
        help="Substring in domain, exact name, or *.org style suffix",
    )
    candidates = st.text_area("Domains to check (one per line)", placeholder="facebook.com\nexample.org")
    if st.button("Block all that match pattern"):
        if pattern and candidates:
            matched = 0
            for line in candidates.strip().splitlines():
                dom = clean_url(line.strip())
                if dom and domain_matches_pattern(dom, pattern):
                    ok, _ = block_website(dom)
                    if ok:
                        matched += 1
            st.success(f"Pattern matched and blocked {matched} site(s)")

with tab_list:
    st.header("Blocked websites")
    sites = get_blocked_sites()
    if not sites:
        st.info("No websites blocked.")
    else:
        st.info(f"Total: {len(sites)}")
        for site in sites:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.text(site)
            with col_b:
                if st.button("Remove", key=f"unblock_{site}"):
                    ok, msg = unblock_website(site)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

with tab_scan:
    st.header("Scan a page before blocking")
    st.write("Loads the URL, shows title and any keyword matches in the page text.")
    probe = st.text_input("URL or domain", placeholder="https://example.com")
    if st.button("Scan page"):
        if probe:
            with st.spinner("Loading page…"):
                result = scrape_page(probe)
            if not result["ok"]:
                st.error(result["error"])
            else:
                st.session_state["scan_result"] = result
    if "scan_result" in st.session_state:
        result = st.session_state["scan_result"]
        st.write(f"**Domain:** {result['domain']}")
        st.write(f"**Title:** {result['title']}")
        if result["keyword_hits"]:
            st.warning("Keywords found: " + ", ".join(result["keyword_hits"]))
        else:
            st.info("No distraction keywords in page text.")
        if result["suggest_block"]:
            st.caption("You may want to block this site.")
        if st.button("Block this domain", key="block_after_scan"):
            ok, msg = block_website(result["domain"])
            show_result(ok, msg)
