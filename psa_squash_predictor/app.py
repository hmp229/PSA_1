# app.py
# ---------------------------------------------------------------
# PSA Squash Match Predictor — Streamlit web app (Python)
# Data source: PSA official website pages only (rankings & player pages)
# Prediction baseline: Joeri Hapers' historical matches, rankings & form
# ---------------------------------------------------------------
# NOTE: This app scrapes **only** psaworldtour.com pages.
# It is designed to be defensive against minor HTML changes and to fail loudly
# (with clear error messages) if a player cannot be located on PSA pages.
# ---------------------------------------------------------------

import re
import math
import time
import json
import random
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np

import streamlit as st

# -------------------------
# Configuration & Constants
# -------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_TIMEOUT = 20
RETRY_COUNT = 3
RETRY_BACKOFF = 1.5

PSA_BASE = "https://www.psaworldtour.com"
RANKINGS_URLS_MEN = [
    f"{PSA_BASE}/rankings/",
    "https://psaworldtour.com/rankings/",
]
PLAYER_PATH_HINT = "/players/view/"

# App Defaults
DEFAULT_BASE_PLAYER = "Joeri Hapers"
DEFAULT_GENDER = "men"  # predictions built for men's tour context by default
RECENT_WINDOW = 12  # number of recent matches to assess "form"
H2H_LOOKBACK = 50   # max matches to consider in head-to-head pull from pages

# -------------------------
# Data Models
# -------------------------
@dataclass
class Player:
    name: str
    gender: str
    profile_url: str
    rank: Optional[int]
    nationality: Optional[str] = None
    psa_id: Optional[str] = None

@dataclass
class Match:
    date: datetime
    player: str
    opponent: str
    result: str  # 'W' or 'L'
    rounds: Optional[str]
    event: Optional[str]
    score: Optional[str]
    opponent_rank: Optional[int] = None

# -------------------------
# Utility — resilient HTTP fetch with backoff
# -------------------------

def fetch_url(url: str) -> requests.Response:
    # Normalise any mistaken domains (common typo: psasquashtour.com)
    url = re.sub(r"https?://(www\.)?psasquashtour\.com", PSA_BASE, url, flags=re.I)
    last_exc = None
    for i in range(RETRY_COUNT):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp
            elif 400 <= resp.status_code < 500:
                # Hard fail for client errors (likely not recoverable)
                resp.raise_for_status()
        except Exception as e:
            last_exc = e
        sleep_for = (RETRY_BACKOFF ** i) + random.random() * 0.25
        time.sleep(sleep_for)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to fetch {url}")

# -------------------------
# PSA Scrapers
# -------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def scrape_rankings_men() -> pd.DataFrame:
    """Scrape men's PSA rankings table from official pages.
    Returns a DataFrame with columns: [rank, name, profile_url, nationality]
    """
    rows = []
    last_error = None
    for url in RANKINGS_URLS_MEN:
        try:
            resp = fetch_url(url)
            soup = BeautifulSoup(resp.text, "lxml")
            # Try different possible table/selectors (defensive parsing)
            tables = soup.select("table")
            if not tables:
                # Some pages render cards — also support list/grid layouts
                cards = soup.select("a[href*='/players/view/']")
                for a in cards:
                    name = a.get_text(strip=True)
                    href = a.get("href"); profile_url = href if href.startswith("http") else PSA_BASE + href
                    # Try to find rank near the anchor
                    rank_text = None
                    parent_text = a.find_parent().get_text(" ", strip=True) if a.find_parent() else ""
                    m = re.search(r"#?(\d{1,3})", parent_text)
                    if m:
                        rank_text = m.group(1)
                    rows.append({
                        "rank": int(rank_text) if rank_text and rank_text.isdigit() else None,
                        "name": name,
                        "profile_url": profile_url,
                        "nationality": None,
                    })
                if rows:
                    break
                continue

            # Prefer the first sizable table
            table = max(tables, key=lambda t: len(t.find_all("tr")))
            for tr in table.select("tbody tr") or table.select("tr"):
                tds = tr.find_all(["td","th"])
                if len(tds) < 2:
                    continue
                text_cells = [td.get_text(" ", strip=True) for td in tds]
                # Rank is likely in first cell
                rank = None
                try:
                    rank = int(re.sub(r"[^0-9]", "", text_cells[0]))
                except Exception:
                    rank = None
                # Find player link
                a = tr.find("a", href=re.compile(PLAYER_PATH_HINT))
                if not a:
                    continue
                name = a.get_text(strip=True)
                href = a.get("href"); profile_url = href if href.startswith("http") else PSA_BASE + href
                # Nationality often present as flag/title attribute nearby
                nat = None
                flag = tr.select_one("img[alt][src*='flag']") or tr.select_one("img[alt]")
                if flag and flag.has_attr("alt"):
                    nat = flag["alt"].strip()
                rows.append({
                    "rank": rank,
                    "name": name,
                    "profile_url": profile_url,
                    "nationality": nat,
                })
            if rows:
                break
        except Exception as e:
            last_error = e
            continue
    if not rows:
        raise RuntimeError(
            "Unable to scrape PSA men's rankings from official pages. "
            f"Last error: {last_error}"
        )
    df = pd.DataFrame(rows).drop_duplicates(subset=["name"]).reset_index(drop=True)
    # Clean names for matching
    df["name_clean"] = df["name"].str.replace(r"\s+", " ", regex=True).str.strip().str.lower()
    return df

@st.cache_data(show_spinner=False, ttl=3600)
def resolve_player_by_name(name: str, gender: str = "men") -> Player:
    name_clean = re.sub(r"\s+", " ", name).strip().lower()
    if gender != "men":
        raise NotImplementedError("This demo currently supports men's tour scraping.")
    rankings = scrape_rankings_men()
    match = rankings[rankings["name_clean"] == name_clean]
    if match.empty:
        # Try partial match if unique
        partial = rankings[rankings["name_clean"].str.contains(re.escape(name_clean))]
        if len(partial) == 1:
            match = partial
        else:
            raise ValueError(
                f"Player '{name}' was not found in the latest PSA men's rankings fetched from official pages."
            )
    row = match.iloc[0]
    # Extract PSA numeric id if present in URL
    psa_id = None
    m = re.search(r"/players/view/(\d+)", row["profile_url"])  # typical pattern
    if m:
        psa_id = m.group(1)
    return Player(
        name=row["name"],
        gender=gender,
        profile_url=row["profile_url"],
        rank=int(row["rank"]) if pd.notna(row["rank"]) else None,
        nationality=row.get("nationality"),
        psa_id=psa_id,
    )

@st.cache_data(show_spinner=False, ttl=3600)
def scrape_player_matches(player: Player, limit: Optional[int] = None) -> List[Match]:
    """Scrape match history from the player's PSA profile page (official).
    Returns recent matches (descending by date).
    """
    resp = fetch_url(player.profile_url)
    soup = BeautifulSoup(resp.text, "lxml")

    # Find links/tabs that lead to matches/results if not directly on page
    results_section = None
    # Attempt common containers
    for sel in [
        "section:has(h2:contains('Results'))",
        "section:has(h3:contains('Results'))",
        "div#results",
        "div.results",
    ]:
        try:
            results_section = soup.select_one(sel)
            if results_section:
                break
        except Exception:
            pass

    # Fallback: search for table with headers like Date / Opponent / Result / Event
    if results_section is None:
        candidate_tables = []
        for table in soup.select("table"):
            head = table.find("thead") or table.find("tr")
            txt = head.get_text(" ", strip=True).lower() if head else ""
            if any(k in txt for k in ["date","opponent","result","event"]):
                candidate_tables.append(table)
        if candidate_tables:
            results_section = candidate_tables[0]

    if results_section is None:
        # Try to follow a "Results" tab if present
        link = soup.find("a", string=re.compile("Results", re.I))
        if link and link.get("href"):
            url = link.get("href"); url = url if url.startswith("http") else PSA_BASE + url
            resp = fetch_url(url)
            soup = BeautifulSoup(resp.text, "lxml")
            results_section = soup

    if results_section is None:
        raise RuntimeError(f"Could not locate Results/Matches section on PSA page for {player.name}.")

    matches: List[Match] = []
    # Parse rows
    for tr in results_section.select("tbody tr") or results_section.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        cells = [td.get_text(" ", strip=True) for td in tds]
        row_text = " | ".join(cells)
        # Heuristic mapping
        # Try to identify fields by keywords/positions
        date_obj = None
        # date candidates
        for c in cells[:2]:
            try:
                date_obj = pd.to_datetime(c, errors="raise").to_pydatetime()
                break
            except Exception:
                continue
        opponent = None
        opp_a = tr.find("a", href=re.compile(PLAYER_PATH_HINT))
        if opp_a:
            opponent = opp_a.get_text(strip=True)
        else:
            # fall back to a cell that looks like a name (contains space & letters)
            for c in cells:
                if re.search(r"[A-Za-z]+\s+[A-Za-z]+", c) and not re.search(r"\d", c):
                    opponent = c; break
        event = None
        event_candidates = tr.find_all("a", href=True)
        if event_candidates:
            # choose non-player link text as event
            for a in event_candidates:
                if not re.search(PLAYER_PATH_HINT, a.get("href","")):
                    event = a.get_text(strip=True)
                    break
        score = None
        m_score = re.search(r"(\d+-\d+)(?:,\s*\d+-\d+)*", row_text)
        if m_score:
            score = m_score.group(0)
        # Result W/L — look for explicit markers or infer from first number dominance
        result = None
        if any("won" in c.lower() for c in cells):
            result = "W"
        elif any("lost" in c.lower() for c in cells):
            result = "L"
        # Fallback: if score looks like 3-1, it's a win if first number > second
        if not result and score:
            try:
                first = score.split(",")[0]
                a,b = [int(x) for x in first.split("-")[:2]]
                result = "W" if a>b else "L"
            except Exception:
                pass
        # Round (R32, QF, SF, F, etc.)
        rounds = None
        for c in cells:
            if re.fullmatch(r"(R\d+|QF|SF|F|Q|Q1|Q2|Q3|Q\d+)", c):
                rounds = c; break
        if not (date_obj and opponent and result):
            continue
        matches.append(Match(
            date=date_obj,
            player=player.name,
            opponent=opponent,
            result=result,
            rounds=rounds,
            event=event,
            score=score,
            opponent_rank=None,
        ))
    # sort newest first
    matches.sort(key=lambda m: m.date, reverse=True)
    if limit:
        matches = matches[:limit]
    return matches

# -------------------------
# Feature Engineering & Simple Model
# -------------------------

def compute_recent_form(matches: List[Match], window: int = RECENT_WINDOW) -> float:
    if not matches:
        return 0.5
    recent = matches[:window]
    wins = sum(1 for m in recent if m.result == "W")
    return wins / max(1, len(recent))

@st.cache_data(show_spinner=False, ttl=3600)
def build_name_to_rank_map(gender: str = "men") -> Dict[str, int]:
    """Build {name: rank} from PSA rankings. If rankings page cannot be parsed,
    return an empty map so the app can still run when players are provided by URL.
    """
    mapping: Dict[str, int] = {}
    try:
        df = scrape_rankings_men()
        for _, r in df.iterrows():
            if pd.notna(r["rank"]) and r["name"]:
                mapping[r["name"]] = int(r["rank"]) if pd.notna(r["rank"]) else None
    except Exception:
        # graceful degradation when rankings page is JS-rendered/blocked
        mapping = {}
    return mapping



def attach_opponent_ranks(matches: List[Match], name_to_rank: Dict[str, int]) -> None:
    for m in matches:
        if m.opponent in name_to_rank:
            m.opponent_rank = name_to_rank[m.opponent]


def head_to_head(base_matches: List[Match], base_name: str, opp_name: str) -> Tuple[int,int]:
    w = sum(1 for m in base_matches if m.opponent == opp_name and m.result == "W")
    l = sum(1 for m in base_matches if m.opponent == opp_name and m.result == "L")
    return w, l


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def predict_probability(
    base_player: Player,
    opp_player: Player,
    base_matches: List[Match],
    opp_matches: List[Match],
    name_to_rank: Dict[str, int],
    weights: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    # Feature 1: Ranking difference (positive if base better ranked i.e., lower number)
    base_rank = base_player.rank or 999
    opp_rank = opp_player.rank or 999
    rank_diff = (opp_rank - base_rank) / 100.0  # scale

    # Feature 2: Recent form difference
    base_form = compute_recent_form(base_matches)
    opp_form = compute_recent_form(opp_matches)
    form_diff = base_form - opp_form

    # Feature 3: H2H win rate vs opponent
    w, l = head_to_head(base_matches, base_player.name, opp_player.name)
    total = w + l
    h2h = (w / total) if total > 0 else 0.5

    # Feature 4: Strength of opposition (average opponent rank of last N)
    def avg_opp_rank(ms: List[Match]) -> float:
        vals = [m.opponent_rank for m in ms if m.opponent_rank is not None]
        return float(np.mean(vals)) if vals else 300.0
    attach_opponent_ranks(base_matches, name_to_rank)
    attach_opponent_ranks(opp_matches, name_to_rank)
    base_sos = avg_opp_rank(base_matches[:RECENT_WINDOW])
    opp_sos = avg_opp_rank(opp_matches[:RECENT_WINDOW])
    sos_diff = (opp_sos - base_sos) / 100.0  # positive if base faced tougher schedule

    # Linear model
    z = (
        weights["intercept"]
        + weights["rank_diff"] * rank_diff
        + weights["form_diff"] * form_diff
        + weights["h2h"] * (h2h - 0.5)
        + weights["sos_diff"] * sos_diff
    )
    p = logistic(z)

    details = {
        "base_rank": base_rank,
        "opp_rank": opp_rank,
        "rank_diff": rank_diff,
        "base_form": base_form,
        "opp_form": opp_form,
        "form_diff": form_diff,
        "h2h_win_rate": h2h,
        "sos_diff": sos_diff,
        "z": z,
    }
    return p, details

# -------------------------
# Streamlit UI
# -------------------------

st.set_page_config(
    page_title="PSA Squash Match Predictor",
    page_icon="🥎",
    layout="wide",
)

st.title("PSA Squash Match Predictor")
st.caption("All data scraped from PSA official website pages. Baseline: Joeri Hapers.")

with st.sidebar:
    st.header("Setup")
    gender = st.selectbox("Tour", ["men"], index=0, help="This demo targets men's tour.")
    base_player_name = st.text_input("Base player (name or PSA profile URL)", value=DEFAULT_BASE_PLAYER)
    opponent_name = st.text_input("Opponent player (name or PSA profile URL)", value="")

    st.subheader("Model Weights")
    w_intercept = st.slider("Intercept", -2.0, 2.0, 0.0, 0.05)
    w_rank = st.slider("Weight: Ranking diff", -4.0, 4.0, 1.4, 0.1)
    w_form = st.slider("Weight: Form diff", -4.0, 4.0, 2.0, 0.1)
    w_h2h = st.slider("Weight: H2H", -4.0, 4.0, 1.0, 0.1)
    w_sos = st.slider("Weight: Strength-of-Schedule diff", -4.0, 4.0, 0.6, 0.1)

    run_btn = st.button("Predict", type="primary")

st.markdown(
    """
    **How it works**  
    1) We fetch PSA world rankings and resolve exact player names from official pages.  
    2) We open each player's PSA profile and parse their match history (recent first).  
    3) We compute features (ranking difference, recent form, head‑to‑head, strength of schedule).  
    4) We combine them in a simple logistic model you can tune with sliders.  
    """
)

st.divider()

if run_btn:
    try:
        # Resolve players: allow PSA profile URL OR official rankings name
        url_pat = r"https?://(www\.)?psaworldtour\.com/players/view/\d+"


        def make_player_from_url(url: str) -> Player:
            pid_m = re.search(r"/players/view/(\d+)", url)
            pid = pid_m.group(1) if pid_m else None
            display_name = url
            try:
                resp = fetch_url(url)
                soup = BeautifulSoup(resp.text, "lxml")
                h = (soup.find("h1") or soup.find("h2") or soup.title)
                if h:
                    display_name = h.get_text(strip=True)
            except Exception:
                pass
            return Player(name=display_name, gender=gender, profile_url=url, rank=None, psa_id=pid)


        if re.match(url_pat, base_player_name.strip()):
            base_player = make_player_from_url(base_player_name.strip())
        else:
            base_player = resolve_player_by_name(base_player_name, gender)

        if re.match(url_pat, opponent_name.strip()):
            opp_player = make_player_from_url(opponent_name.strip())
        else:
            opp_player = resolve_player_by_name(opponent_name, gender)

    except NotImplementedError as e:
        st.error(str(e))
        st.stop()
    except ValueError as e:
        st.error(f"❌ {e}\n\nEnsure the name matches the PSA rankings exactly (official spelling).")
        st.stop()
    except Exception as e:
        st.error(f"Failed to resolve players from PSA pages. Details: {e}")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Base Player")
        st.write(f"**{base_player.name}**")
        st.write(f"Rank: {base_player.rank if base_player.rank else '—'}  •  PSA ID: {base_player.psa_id or '—'}")
        st.link_button("Open PSA Profile", base_player.profile_url)
    with col2:
        st.subheader("Opponent")
        st.write(f"**{opp_player.name}**")
        st.write(f"Rank: {opp_player.rank if opp_player.rank else '—'}  •  PSA ID: {opp_player.psa_id or '—'}")
        st.link_button("Open PSA Profile", opp_player.profile_url)

    with st.spinner("Scraping match histories from PSA official pages…"):
        try:
            base_matches = scrape_player_matches(base_player, limit=H2H_LOOKBACK)
            opp_matches = scrape_player_matches(opp_player, limit=H2H_LOOKBACK)
        except Exception as e:
            st.error(f"Could not scrape match histories: {e}")
            st.stop()

    if not base_matches:
        st.error(f"No matches found on PSA page for {base_player.name}.")
        st.stop()
    if not opp_matches:
        st.warning(f"No matches found on PSA page for {opp_player.name}. We'll still predict using rankings and base player's form.")

    # Build rank mapping & compute
    name_to_rank = build_name_to_rank_map(gender)

    weights = {
        "intercept": w_intercept,
        "rank_diff": w_rank,
        "form_diff": w_form,
        "h2h": w_h2h,
        "sos_diff": w_sos,
    }

    p, details = predict_probability(
        base_player, opp_player, base_matches, opp_matches, name_to_rank, weights
    )

    st.success(f"**Predicted probability {base_player.name} beats {opp_player.name}: {p*100:.1f}%**")

    # Show details
    with st.expander("Model features & internals"):
        st.json(details)

    # Tabular views
    def matches_to_df(ms: List[Match]) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "Date": m.date.strftime("%Y-%m-%d"),
                "Opponent": m.opponent,
                "Result": m.result,
                "Round": m.rounds,
                "Event": m.event,
                "Score": m.score,
                "Opponent Rank": m.opponent_rank,
            }
            for m in ms
        ])

    t1, t2 = st.tabs([f"{base_player.name} — recent", f"{opp_player.name} — recent"])
    with t1:
        st.dataframe(matches_to_df(base_matches), use_container_width=True)
    with t2:
        st.dataframe(matches_to_df(opp_matches), use_container_width=True)

    # H2H summary
    w, l = head_to_head(base_matches, base_player.name, opp_player.name)
    st.info(f"Head‑to‑Head (from {base_player.name}'s PSA page): {w}–{l}")

else:
    st.info("Enter an opponent name (as on PSA rankings) and click **Predict**.")

# -------------------------
# Developer / Debug section (optional)
# -------------------------
with st.expander("Diagnostics"):
    st.caption("For debugging scraping issues.")
    try:
        df_rank = scrape_rankings_men()
        st.write(f"Fetched {len(df_rank)} ranked players from PSA official pages (men).")
        st.dataframe(df_rank.head(20), use_container_width=True)
    except Exception as e:
        st.error(f"Rankings scrape error: {e}")

# -------------------------
# End of app.py
# -------------------------
