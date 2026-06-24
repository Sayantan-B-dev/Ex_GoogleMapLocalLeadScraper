import argparse
import time
import random
import re
import os
import pandas as pd

from playwright.sync_api import sync_playwright


def random_sleep(a=2, b=4):
    time.sleep(random.uniform(a, b))


def clean_text(text):
    if not text:
        return ""

    junk_chars = [
        "", "", "", "", "",
        "", "", "\n", "\r", "\t"
    ]

    for j in junk_chars:
        text = text.replace(j, " ")

    return " ".join(text.split()).strip()


def safe_locator_text(locator):
    try:
        if locator.count() > 0:
            return clean_text(
                locator.first.inner_text(timeout=3000)
            )
    except:
        pass

    return ""


def extract_business_data(page):
    data = {
        "search_query": "",
        "name": "",
        "category": "",
        "rating": "",
        "reviews": "",
        "address": "",
        "phone": "",
        "website": "",
        "email": "",
        "city": "",
        "state": "",
        "maps_url": page.url
    }

    # ---------- Name ----------
    try:
        data["name"] = clean_text(
            page.locator("h1.DUwDvf").first.inner_text(timeout=5000)
        )
    except:
        pass

    # ---------- Category ----------
    try:
        category = page.locator(
            'button[jsaction*="pane.rating.category"]'
        )
        data["category"] = safe_locator_text(category)
    except:
        pass

    # ---------- Rating ----------
    try:
        rating = page.locator(
            'div.F7nice span[aria-hidden="true"]'
        )
        data["rating"] = safe_locator_text(rating)
    except:
        pass

    # ---------- Reviews ----------
    try:
        reviews = page.locator(
            'button[jsaction*="pane.reviewChart.moreReviews"]'
        )
        txt = safe_locator_text(reviews)
        m = re.search(r'([\d,]+)', txt)
        if m:
            data["reviews"] = m.group(1)
    except:
        pass

    # ---------- Address ----------
    try:
        address = page.locator(
            'button[data-item-id="address"]'
        )
        data["address"] = safe_locator_text(address)
    except:
        pass

    # ---------- Phone ----------
    try:
        phone = page.locator(
            'button[data-item-id^="phone"]'
        )
        txt = safe_locator_text(phone)
        txt = re.sub(r'[^0-9+ ]', '', txt)
        data["phone"] = txt.strip()
    except:
        pass

    # ---------- Website ----------
    try:
        website = page.locator(
            'a[data-item-id="authority"]'
        )
        if website.count() > 0:
            href = website.first.get_attribute("href")
            if href:
                data["website"] = href
    except:
        pass

    # ---------- Email ----------
    try:
        email_btn = page.locator(
            'button[data-item-id="email"]'
        )
        if email_btn.count() > 0:
            txt = safe_locator_text(email_btn)
            if txt and "@" in txt:
                data["email"] = txt
            else:
                href = email_btn.first.get_attribute("href")
                if href and href.startswith("mailto:"):
                    data["email"] = href.replace("mailto:", "").split("?")[0]
    except:
        pass
    if not data["email"]:
        try:
            email_link = page.locator(
                'a[data-item-id="email"]'
            )
            if email_link.count() > 0:
                href = email_link.first.get_attribute("href")
                if href and href.startswith("mailto:"):
                    data["email"] = href.replace("mailto:", "").split("?")[0]
        except:
            pass

    # ---------- City / State ----------
    try:
        if data["address"]:
            parts = [p.strip() for p in data["address"].split(",")]
            if len(parts) >= 2:
                data["city"] = parts[-2]
            if len(parts) >= 1:
                state = re.sub(r"\d{6}", "", parts[-1])
                data["state"] = state.strip()
    except:
        pass

    return data


def scroll_results(page):
    print("Scrolling search results...")
    random_sleep(3, 5)

    try:
        panel = page.locator('div[role="feed"]').first
        previous = 0
        same = 0
        max_scrolls = 100

        for scroll_count in range(max_scrolls):
            panel.evaluate("(el) => el.scrollBy(0, 1500)")
            random_sleep(3, 5)

            cards = page.locator("a.hfpxzc")
            current = cards.count()
            print(f"  Scrolled {scroll_count+1}: {current} results loaded")

            if current == previous:
                same += 1
            else:
                same = 0

            if same >= 5:
                print(f"  No new results after {same} scrolls, stopping")
                break

            if current >= 180:
                print(f"  Reached ~{current} results, stopping")
                break

            previous = current

        print(f"Total results found: {previous}")

    except Exception as e:
        print("Scroll error:", e)


def load_queries(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return [q.strip() for q in f if q.strip()]


def load_done_queries(done_file):
    if not os.path.exists(done_file):
        return set()
    with open(done_file, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def mark_done(done_file, query):
    with open(done_file, "a", encoding="utf-8") as f:
        f.write(query + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Google Maps Lead Scraper"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input query file (.txt)"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output CSV file"
    )
    parser.add_argument(
        "--profile", default=None,
        help="Chrome user data directory for persistent profile"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--done", default=None,
        help="File to track completed queries for resume"
    )
    args = parser.parse_args()

    done_file = args.done or (args.output + ".done")
    all_rows = []

    # Resume: load existing rows from CSV
    if os.path.exists(args.output):
        try:
            all_rows = pd.read_csv(args.output).to_dict("records")
            print(f"Loaded {len(all_rows)} existing rows from {args.output}")
        except:
            pass

    # Resume: load completed queries
    done_queries = load_done_queries(done_file)
    query_log = []
    if done_queries:
        print(f"Resuming: {len(done_queries)} queries already completed")

    queries = load_queries(args.input)
    queries = [q for q in queries if q not in done_queries]
    print(f"Queued: {len(queries)} queries to process")

    if not queries:
        print("All queries already completed. Nothing to do.")
        return

    with sync_playwright() as p:
        if args.profile:
            print(f"Using persistent profile: {args.profile}")
            context = p.chromium.launch_persistent_context(
                user_data_dir=args.profile,
                headless=args.headless,
                slow_mo=500,
                viewport={"width": 1400, "height": 900}
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.set_viewport_size({"width": 1400, "height": 900})
        else:
            browser = p.chromium.launch(
                headless=args.headless,
                slow_mo=500
            )
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1400, "height": 900})

        try:
            for query in queries:
                print("\n" + "=" * 70)
                print("SEARCH:", query)
                print("=" * 70)

                try:
                    search_url = (
                        "https://www.google.com/maps/search/"
                        + query.replace(" ", "+")
                    )

                    page.goto(search_url, timeout=90000)
                    random_sleep(8, 12)

                    scroll_results(page)

                    cards = page.locator("a.hfpxzc")
                    total = cards.count()
                    print(f"Businesses found: {total}")

                    for i in range(total):
                        try:
                            print(f"\nOpening business {i+1}/{total}")

                            cards = page.locator("a.hfpxzc")
                            if i >= cards.count():
                                break

                            card = cards.nth(i)
                            card.scroll_into_view_if_needed()
                            random_sleep(1, 2)
                            card.click(force=True)

                            page.wait_for_timeout(4000)

                            try:
                                page.wait_for_selector("h1.DUwDvf", timeout=10000)
                            except:
                                print("Business panel not loaded")
                                continue

                            row = extract_business_data(page)
                            row["search_query"] = query

                            if row["name"] == "" or row["name"] == "Results":
                                print("Skipped invalid row")
                                continue

                            print("Name:", row["name"])
                            all_rows.append(row)

                            df = pd.DataFrame(all_rows)
                            df.drop_duplicates(subset=["name", "phone", "address"], inplace=True)
                            df.to_csv(args.output, index=False, encoding="utf-8-sig")

                        except Exception as e:
                            print(f"Business {i+1} failed:", e)

                    mark_done(done_file, query)

                except Exception as e:
                    print("Query failed:", e)
        finally:
            context.close()
            if not args.profile:
                # browser.close() is redundant when using new_context
                pass

    df = pd.DataFrame(all_rows)
    df.drop_duplicates(subset=["name", "phone", "address"], inplace=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"\nDONE — {len(df)} unique leads saved to {args.output}")


if __name__ == "__main__":
    main()
