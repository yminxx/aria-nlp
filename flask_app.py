# flask_app.py
import os
import json
import re
import random
from dotenv import load_dotenv
from flask import Flask, request, render_template

# ========== ENVIRONMENT SETUP ==========
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit("Set GEMINI_API_KEY in environment or .env")

# Import the GenAI client
try:
    from google import genai
except Exception as e:
    raise SystemExit("google-genai missing. Install with: pip install google-genai")

# Flask app setup
app = Flask(__name__)
CLIENT = genai.Client(api_key=API_KEY)

# ========== DATABASE LOADING ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "Export", "pc_database.json")

if not os.path.exists(DB_PATH):
    raise FileNotFoundError(
        f"Database not found at {DB_PATH}. "
        "Create an 'Export' folder beside flask_app.py and place pc_database.json inside it."
    )

with open(DB_PATH, "r", encoding="utf-8") as f:
    DATABASE = json.load(f)

app.logger.info(
    f"Loaded component database from {DB_PATH} "
    f"({len(DATABASE.get('cpus', []))} CPUs, {len(DATABASE.get('motherboards', []))} motherboards, etc.)"
)

# ---------- Greeting detection helpers ----------
GREET_PAT = re.compile(
    r"\b(h+i+|h+e+l+l+o+|hey+|hiya+|yo+|sup|hi+ya+|hello+)\b",
    flags=re.IGNORECASE,
)
QUESTION_WORDS = {
    "what",
    "who",
    "where",
    "when",
    "why",
    "how",
    "is",
    "are",
    "do",
    "does",
    "latest",
    "recommend",
    "compatible",
    "compatibility",
    "explain",
    "tell",
}


def looks_like_greeting(text: str) -> bool:
    if not text or len(text.strip()) == 0:
        return False
    low = text.lower()
    tokens = re.findall(r"\w+", low)
    if any(q in tokens for q in QUESTION_WORDS):
        return False
    if GREET_PAT.search(text):
        return True
    if len(tokens) <= 2 and len(text.strip()) <= 12:
        for g in ("hi", "hello", "hey", "hiya", "yo", "sup"):
            if g in low:
                return True
    return False


# ========== ROUTES ==========
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/check-compatibility", methods=["POST"])
def check_compat():
    data = request.get_json(force=True)
    query = (data.get("query") or "").strip()

    # --- Deterministic handler: SMFP Computer Trading info ---
    if re.search(
        r"\b(smfp|smfp computer|smfp computer trading)\b", query, flags=re.IGNORECASE
    ):
        desc = (
            "SMFP Computer Trading is a trusted computer hardware retailer based in Quiapo, Manila. "
            "They are known for providing quality PC components and excellent customer service, "
            "serving both gamers and builders looking for reliable parts at fair prices."
        )
        info = (
            "\n\nFor more info:\n"
            "Address: 594 Nepomuceno St, Quiapo, Manila\n"
            "Email: sherlopilarco@yahoo.com\n"
            "Contact: 0949-883-7098\n"
            "Closing hours: 6:00 PM – 6:30 PM"
        )
        return (desc + info, 200, {"Content-Type": "text/plain; charset=utf-8"})

    # --- List and Recommendation Handler (latest hardware OR from database) ---
    if re.search(
        r"\b(latest|new|newest|recent|2025|2024|best|recommended)\b",
        query,
        flags=re.IGNORECASE,
    ):
        # --- Latest hardware info via Gemini (outside database) ---
        try:
            gemini_prompt = (
                f"List the latest {query} available as of 2025. "
                f"If 2025 data isn't available yet, start your response with "
                f"'Sorry, data for 2025 isn’t available yet. Here’s a list of 2024 models instead:' "
                f"then list 4 to 6 items in this format:\n\n"
                f"- **Product Name (Category)**\n"
                f"  - Key spec 1\n"
                f"  - Key spec 2\n"
                f"  - Recommended use\n"
                f"  - Compatibility or brief remark\n\n"
                f"Keep it short, factual, and neatly formatted in plain Markdown bullets. "
                f"Do NOT use emojis or tables. Provide 4–6 items where possible."
            )
            resp = CLIENT.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=gemini_prompt,
            )
            
        except Exception as e:
            app.logger.warning("Gemini latest list failed: %s", e)
            # fall through to DB-based matching if Gemini fails

    # --- Database-based list recommendation (e.g., AM4 motherboards, DDR4 RAM) ---
    db_keywords = {
        "motherboards": ["motherboard", "am4", "am5", "b450", "b550", "x570", "b650"],
        "cpus": ["cpu", "processor", "ryzen", "intel", "core", "i5", "i7", "i9"],
        "gpus": ["gpu", "graphics", "rtx", "gtx", "rx", "radeon"],
        "rams": ["ram", "memory", "ddr4", "ddr5"],
        "storages": ["ssd", "nvme", "hdd", "storage", "hard drive"],
        "psus": ["psu", "power supply", "watt"],
        "coolers": ["cooler", "aio", "liquid", "air cooler"],
    }

    matched_cat = None
    for cat, kws in db_keywords.items():
        if any(kw in query.lower() for kw in kws):
            matched_cat = cat
            break

    if matched_cat:
        items = DATABASE.get(matched_cat, [])
        if not items:
            return (
                f"I couldn’t find any {matched_cat} in the database.",
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )

        # Try to filter (AM4, DDR4, model tokens, etc.)
        filtered = []
        qlow = query.lower()
        qtokens = set(re.findall(r"\w+", qlow))
        for it in items:
            dn = (it.get("displayName") or "").lower()
            # match if any token from the query appears in the displayName OR common keywords match
            if qtokens & set(re.findall(r"\w+", dn)):
                filtered.append(it)

        shown = filtered if filtered else items[:6]
        intro = f"Here are some {matched_cat.replace('s','')}s from the database that match your request:"
        bullets = "\n".join([f"- **{it.get('displayName')}**" for it in shown[:8]])

        return (
            f"{intro}\n\n{bullets}",
            200,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    # --- Quick deterministic "specs" handler (returns DB specs as invisible-border table) ---
    if re.search(
        r"\b(specs|specifications|spec|details|configuration)\b",
        query,
        flags=re.IGNORECASE,
    ):
        qlow = query.lower()

        def find_component(name_lower):
            for cat in (
                "motherboards",
                "cpus",
                "gpus",
                "rams",
                "storages",
                "psus",
                "coolers",
                "ssds",
                "nvmes",
                "hdds",
                "ssds",
                "storages",
            ):
                items = DATABASE.get(cat) or []
                for item in items:
                    dn = (item.get("displayName") or "").lower()
                    if name_lower in dn or dn in name_lower:
                        return item
            for cat, items in DATABASE.items():
                if isinstance(items, list):
                    for item in items:
                        dn = (item.get("displayName") or "").lower()
                        if name_lower in dn or dn in name_lower:
                            return item
            return None

        # --- Improved matching: normalize + token-overlap + fuzzy fallback ---
        found = None
        name_norm = re.sub(r"[^\w\s]", " ", query).lower().strip()

        all_names = []
        for cat in DATABASE:
            items = DATABASE.get(cat) or []
            for it in items:
                dn = it.get("displayName", "") or ""
                dn_norm = re.sub(r"[^\w\s]", " ", dn).lower().strip()
                if dn:
                    all_names.append((dn, dn_norm, it))

        all_names.sort(key=lambda x: -len(x[0] or ""))

        for dn, dn_norm, item in all_names:
            if dn_norm and (dn_norm in name_norm or name_norm in dn_norm):
                found = item
                break

        if not found:
            qtokens = set(name_norm.split())
            best = None
            best_score = 0.0
            for dn, dn_norm, item in all_names:
                tokens = set(dn_norm.split())
                if not tokens:
                    continue
                overlap = len(qtokens & tokens)
                score = overlap / len(tokens)
                if score > best_score and overlap >= 1:
                    best_score = score
                    best = (dn_norm, item, score)
            if best and best_score >= 0.35:
                found = best[1]

        if not found:
            try:
                import difflib

                names_norm = [dn_norm for (_, dn_norm, _) in all_names if dn_norm]
                close = difflib.get_close_matches(
                    name_norm, names_norm, n=3, cutoff=0.7
                )
                if close:
                    dn_close = close[0]
                    for dn, dn_norm, item in all_names:
                        if dn_norm == dn_close:
                            found = item
                            break
            except Exception:
                pass

        if not found:
            found = find_component(name_norm)

        if found:
            comp_name = found.get("displayName", "This component")
            brand_name = (found.get("brand") or "").strip()
            price_val = found.get("price")
            category_guess = "component"

            for cat, items in DATABASE.items():
                if isinstance(items, list) and found in items:
                    category_guess = cat
                    break

            usage = "general-purpose builds"
            budget = "mid-range budget"
            try:
                pnum = float(price_val)
                if pnum < 3000:
                    budget = "entry-level budget"
                elif pnum < 10000:
                    budget = "mid-range budget"
                else:
                    budget = "high-end budget"
            except Exception:
                pass

            if category_guess in ("cpus", "gpus"):
                usage = "gaming and productivity setups"
            elif category_guess in ("motherboards", "psus", "rams"):
                usage = "balanced gaming or office builds"
            elif category_guess in ("storages", "ssds", "nvmes", "hdds"):
                usage = "storage expansion or performance upgrades"
            elif category_guess in ("coolers",):
                usage = "cooling high-performance systems"

            # --- Ask Gemini to generate a short 2-sentence BRAND explanation if brand exists,
            #     otherwise fall back to component description ---
            try:
                if brand_name:
                    gemini_prompt = (
                        f"Write a concise two-sentence description of the brand '{brand_name}' "
                        "in the context of PC hardware. Mention what the brand is generally known for "
                        "(e.g., reliability, value, gaming focus, cooling, storage, motherboards, GPUs, etc.). "
                        "Use a neutral, informative tone and keep it exactly two short sentences."
                    )
                else:
                    gemini_prompt = (
                        f"Write a concise two-sentence description of the PC component '{comp_name}'. "
                        "Clearly state what type of component it is and what it does. "
                        "Use a neutral, informative tone and keep it exactly two short sentences."
                    )

                gemini_resp = CLIENT.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=gemini_prompt,
                )
                desc_text = getattr(gemini_resp, "text", "").strip()
                if not desc_text:
                    if brand_name:
                        desc_text = f"{brand_name} is a company that produces PC hardware components. It is known for offering reliable products in its segment."
                    else:
                        desc_text = f"{comp_name} is a computer component. It is designed for use in PC systems."
            except Exception as e:
                app.logger.warning("Gemini short description failed: %s", e)
                if brand_name:
                    desc_text = f"{brand_name} is a company that produces PC hardware components."
                else:
                    desc_text = (
                        f"{comp_name} is a computer component used in PC builds."
                    )

            intro_html = f"<p>{desc_text}</p><p><b>{comp_name} Specifications:</b></p>"

            rows = []
            for k, v in found.items():
                if k in ("displayName", "brand", "id"):
                    continue
                if isinstance(v, bool):
                    val = "Yes" if v else "No"
                elif isinstance(v, (list, tuple)):
                    val = ", ".join(str(x) for x in v)
                else:
                    val = str(v)
                if val.strip() == "":
                    continue
                rows.append((k, val))

            if not rows:
                pass
            else:
                table_html = [
                    '<table style="border-collapse:collapse;">',
                    "<thead><tr>",
                    '<th style="border:none;text-align:left;padding:6px 88px 6px 0;font-weight:600">Category</th>',
                    '<th style="border:none;text-align:left;padding:6px 8px">Details</th>',
                    "</tr></thead>",
                    "<tbody>",
                ]
                for k, val in rows:
                    human_k = re.sub(r"(_|-)+", " ", k).strip()
                    human_k = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", human_k)
                    human_k = human_k.title()
                    table_html.append(
                        f'<tr><td style="border:none;padding:4px 8px 4px 0;vertical-align:top">{human_k}</td>'
                        f'<td style="border:none;padding:4px 8px;vertical-align:top">{val}</td></tr>'
                    )
                table_html.append("</tbody></table>")
                html = "\n".join(table_html)
                return (
                    intro_html + html,
                    200,
                    {"Content-Type": "text/html; charset=utf-8"},
                )

    # --- Robust deterministic "price" handler (replace previous price handler) ---
    if re.search(
        r"\b(price|how much|cost|how much is|how much does|price of)\b",
        query,
        flags=re.IGNORECASE,
    ):
        import difflib

        def normalize_text(s: str) -> str:
            if not s:
                return ""
            s = "".join(ch for ch in s if ord(ch) >= 32)
            s = s.replace("\u202f", " ").replace("\u00a0", " ")
            s = s.replace("/", " ").replace("\\", " ")
            s = re.sub(r"[^\w\s\-]", " ", s)
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        qnorm = normalize_text(query)
        app.logger.info("Price lookup for query (normalized): %s", qnorm)

        all_items = []
        for cat, items in DATABASE.items():
            if isinstance(items, list):
                for it in items:
                    dn = it.get("displayName", "") or ""
                    all_items.append((normalize_text(dn), it, cat))

        all_items.sort(key=lambda x: -len(x[0]))
        found = None
        for ndn, item, cat in all_items:
            if ndn and (ndn in qnorm or qnorm in ndn):
                found = (item, cat)
                app.logger.info(
                    "Price handler matched by substring: %s (cat=%s)", ndn, cat
                )
                break

        if not found:
            qtokens = set(qnorm.split())
            best = None
            best_score = 0
            for ndn, item, cat in all_items:
                tokens = set(ndn.split())
                if not tokens:
                    continue
                overlap = len(qtokens & tokens)
                score = overlap / len(tokens)
                if score > best_score and overlap >= 1:
                    best_score = score
                    best = (ndn, item, cat, score)
            if best and best_score >= 0.4:
                ndn, item, cat, score = best
                found = (item, cat)
                app.logger.info(
                    "Price handler matched by token overlap: %s (score=%.2f)",
                    ndn,
                    score,
                )

        if not found:
            names = [ndn for ndn, _, _ in all_items if ndn]
            close = difflib.get_close_matches(qnorm, names, n=3, cutoff=0.7)
            if close:
                ndn_close = close[0]
                for ndn, item, cat in all_items:
                    if ndn == ndn_close:
                        found = (item, cat)
                        app.logger.info(
                            "Price handler matched by fuzzy: %s (input=%s)",
                            ndn_close,
                            qnorm,
                        )
                        break

        if found:
            item, cat = found
            price_val = item.get("price")
            app.logger.info(
                "Found item %s in category %s, price field=%s",
                item.get("displayName"),
                cat,
                repr(price_val),
            )
            if price_val is None:
                return (
                    "I don't have a price listed for that component in the database.",
                    200,
                    {"Content-Type": "text/plain; charset=utf-8"},
                )
            try:
                pnum = float(price_val)
                pdisplay = f"₱{int(round(pnum)):,}"
            except Exception:
                pdisplay = str(price_val)
            return (
                f"The price for {item.get('displayName')} is {pdisplay}.",
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )

        q = qnorm
        guessed_cat = None
        if re.search(
            r"\b(ryzen|intel|core i|corei|corei3|corei5|corei7|corei9|xeon|athlon)\b", q
        ):
            guessed_cat = "cpus"
        elif re.search(r"\b(rtx|gtx|rx|radeon|graphics|gpu|graphics card)\b", q):
            guessed_cat = "gpus"
        elif re.search(
            r"\b(b\d+|x\d+|z\d+|h\d+|prime|tuf|pro|mpg|aorus|asus|msi)\b", q
        ):
            guessed_cat = "motherboards"
        elif re.search(r"\b(ddr|ram|memory)\b", q):
            guessed_cat = "rams"
        elif re.search(r"\b(ssd|nvme|sata|hdd|hard drive|storage)\b", q):
            guessed_cat = "storages"
        elif re.search(r"\b(psu|power supply|watt)\b", q):
            guessed_cat = "psus"
        elif re.search(r"\b(cooler|aio|liquid|air cooler|masterliquid|hyper)\b", q):
            guessed_cat = "coolers"

        def price_stats_for_category(cat_name):
            vals = []
            for it in DATABASE.get(cat_name, []) or []:
                v = it.get("price")
                try:
                    vals.append(float(v))
                except Exception:
                    continue
            if not vals:
                return None
            return (min(vals), max(vals))

        stats = None
        if guessed_cat:
            stats = price_stats_for_category(guessed_cat)
            app.logger.info("Guessed category: %s, stats=%s", guessed_cat, stats)
        if not stats and guessed_cat == "storages":
            merged = []
            for k in ("nvmes", "ssds", "hdds", "storages"):
                for it in DATABASE.get(k, []) or []:
                    try:
                        merged.append(float(it.get("price")))
                    except Exception:
                        continue
            if merged:
                stats = (min(merged), max(merged))
        if not stats:
            all_prices = []
            for cat, items in DATABASE.items():
                if isinstance(items, list):
                    for it in items:
                        try:
                            all_prices.append(float(it.get("price")))
                        except Exception:
                            continue
            if all_prices:
                stats = (min(all_prices), max(all_prices))

        if stats:
            pmin, pmax = stats
            try:
                pmin_s = f"₱{int(round(pmin)):,}"
                pmax_s = f"₱{int(round(pmax)):,}"
            except Exception:
                pmin_s = str(pmin)
                pmax_s = str(pmax)
            stores_line = "Prices vary depending on the store. In the Philippines, check SMFP Computer Trading (recommended), PC Express, DynaQuest, EasyPC, or DataBlitz."
            return (
                f"I don't have that exact product in the database. Based on similar items, an estimated price range is {pmin_s} to {pmax_s}. {stores_line}",
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )
        else:
            return (
                "I don't have enough pricing data to estimate a range. Try asking with the exact product name from the list.",
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )

    # --- Greeting handling: only if user actually greeted ---
    if looks_like_greeting(query):
        greet_prompt = (
            "System: You are Aria, a friendly and professional PC-building assistant. "
            "The user has greeted Aria (possibly with informal spelling or repeated letters). "
            "Reply with a short, warm greeting (1 or 2 sentences max) as Aria and offer help about PC components or builds. "
            "Do NOT mention databases or data sources. Keep it varied and natural.\n\n"
            f"User input: {query}\n"
            "Respond only with the greeting (no extra commentary)."
        )
        try:
            resp_g = CLIENT.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=greet_prompt,
            )
            raw_g = getattr(resp_g, "text", None) or str(resp_g)

            def _clean_short(s):
                s = s.strip()
                if s.startswith("```") and s.endswith("```"):
                    parts = s.splitlines()
                    if len(parts) >= 3:
                        s = "\n".join(parts[1:-1])
                if (s.startswith('"') and s.endswith('"')) or (
                    s.startswith("'") and s.endswith("'")
                ):
                    s = s[1:-1]
                try:
                    import unicodedata

                    s = unicodedata.normalize("NFC", s)
                except Exception:
                    pass
                return re.sub(r"^[`\\s]+|[`\\s]+$", "", s)

            return (
                _clean_short(raw_g),
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )
        except Exception as e:
            app.logger.exception("Greeting model call failed")
            return (
                "Hi — I'm Aria. How can I help with PC components or builds today?",
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )

    if not query:
        return (
            "No question provided",
            400,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    # --- Optional: Provide database context to the model ---
    db_summary = json.dumps(
        {
            "motherboards": [
                mb["displayName"] for mb in DATABASE.get("motherboards", [])
            ],
            "cpus": [cpu["displayName"] for cpu in DATABASE.get("cpus", [])],
            "gpus": [gpu["displayName"] for gpu in DATABASE.get("gpus", [])],
            "rams": [ram["displayName"] for ram in DATABASE.get("rams", [])],
            "storages": [s["displayName"] for s in DATABASE.get("storages", [])],
            "psus": [p["displayName"] for p in DATABASE.get("psus", [])],
            "coolers": [c["displayName"] for c in DATABASE.get("coolers", [])],
        },
        ensure_ascii=False,
    )

    # --- STRONG PROMPT RULES (Aria) ---
    prompt = (
        "System: You are Aria, ARsemble's PC-building assistant. "
        "You only answer questions related to computer components, compatibility, or definitions of PC hardware terms.\n\n"
        "Use the provided list of component names to understand what hardware exists. "
        "By default, do NOT mention any database or data source in your responses.\n\n"
        "However, if the user explicitly asks where the data or information comes from, "
        "you may respond politely that the product information is provided by "
        "SMFP Computer — a trusted computer hardware retailer located at "
        "594 J. Nepomuceno St, Quiapo, Manila, 1001 Metro Manila — known for offering quality parts and excellent service.\n\n"
        f"Available parts (for reference): {db_summary}\n\n"
        "Behavior:\n"
        "- If asked about compatibility between hardware (e.g. 'Is CPU X compatible with Motherboard Y?'), "
        "respond in this exact format: 'Yes. <brief reason>' or 'No. <brief reason>'.\n"
        "- When asked for definitions or general PC information (e.g. 'What is a motherboard?'), answer in an educational tone, "
        "using 3 to 5 short sentences. Be clear and concise.\n"
        "- If the user asks for the latest or newest PC components (e.g. 'latest GPU 2025' or 'new CPU this year'), "
        "you may answer using your general market knowledge. "
        "If the requested year is beyond available information, mention the latest year you know (for example, if asked about 2026, give 2025 data instead).\n"
        "- When the question involves CPU vs GPU compatibility, determine compatibility based on performance balance (bottleneck analysis) rather than socket. "
        "State whether the pairing is well-balanced or which side may bottleneck the other, and include an estimated bottleneck percentage (see ranges below). Keep this explanation within 3 to 5 sentences.\n"
        "    * Well-balanced: bottleneck minimal (0–5%).\n"
        "    * CPU-limits-GPU: estimate ~10–30% CPU bottleneck depending on severity.\n"
        "    * GPU-limits-CPU: estimate ~10–20% GPU bottleneck.\n"
        "- If the user asks where to buy PC components or mentions shops, list SMFP Computer first as the top recommended store (include the address), followed by other known computer retailers in the Philippines only (for example: PC Express, DynaQuest, EasyPC, DataBlitz). Describe SMFP Computer positively.\n"
        "- For recommendations, builds, or part-selection guidance, strictly use only the components found in the provided database.\n"
        "- If the question clearly has no relation to PC components or computing hardware, respond with that line. "
        "However, if the question seems like a clarification or follow-up (for example, it refers to something mentioned earlier), "
        "then answer naturally using the previous topic as context.\n"
        "- Do NOT start responses with greetings, introductions, or pleasantries (for example: 'Hi', 'Hello', 'Hey', 'Hi there', 'Hello! Nice to see you'). "
        "Only include a greeting if the user's input was itself a greeting. Otherwise begin directly with the educational or compatibility answer.\n"
        "- Never start responses with introductions like 'I am ARsemble's AI' and do not mention the database unless the user explicitly asks where the data came from.\n"
        "- Keep all responses educational, neutral, and easy to read.\n\n"
        f"User question: {query}"
    )

    try:
        app.logger.info("Calling Gemini for query: %s", query)
        resp = CLIENT.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
    except Exception as e:
        app.logger.exception("Model call failed")
        return (
            "Model call failed: " + str(e),
            502,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    raw_text = getattr(resp, "text", None) or str(resp)
    app.logger.info("Raw model output (truncated): %s", raw_text[:300])

    # --- Output cleaning ---
    def clean_output(s: str) -> str:
        s = s.strip()
        if s.startswith("```") and s.endswith("```"):
            lines = s.splitlines()
            if len(lines) >= 3:
                s = "\n".join(lines[1:-1])
        if (s.startswith('"') and s.endswith('"')) or (
            s.startswith("'") and s.endswith("'")
        ):
            s = s[1:-1]
        try:
            import unicodedata

            s = unicodedata.normalize("NFC", s)
        except Exception:
            pass
        s = re.sub(r"^[`\\s]+", "", s)
        s = re.sub(r"[`\\s]+$", "", s)
        return s

    cleaned = clean_output(raw_text)

    # --- If user did NOT greet but model still prepended a greeting, strip it ---
    try:
        if not looks_like_greeting(query):
            m = re.match(
                r"^\s*(?:hi|hello|hey|hiya|greetings|good morning|good afternoon|good evening)\b[^.?!]{0,200}[.?!]\s*",
                cleaned,
                flags=re.IGNORECASE,
            )
            if m:
                cleaned = cleaned[m.end() :].lstrip()
                cleaned = re.sub(r'^[`"\'\s]+', "", cleaned)
    except Exception:
        pass

    # Try to parse JSON only if model returned JSON; otherwise use cleaned text
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            readable = (
                parsed.get("note")
                or parsed.get("reason")
                or json.dumps(parsed, ensure_ascii=False)
            )
        else:
            readable = json.dumps(parsed, ensure_ascii=False)
    except Exception:
        readable = cleaned

    return (readable, 200, {"Content-Type": "text/plain; charset=utf-8"})


if __name__ == "__main__":
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    app.run(host="0.0.0.0", port=port)
