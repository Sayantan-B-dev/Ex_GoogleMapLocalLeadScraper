
import time
import random
import re
import os
import pandas as pd

from playwright.sync_api import sync_playwright

INPUT_FILE = "google_maps_queries.txt"
OUTPUT_FILE = "google_maps_leads.csv"


# HELPERS

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


# EXTRACT BUSINESS DETAILS

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
        "city": "",
        "state": "",
        "maps_url": page.url
    }

    print("Current URL:", page.url)

    # ---------- Name ----------
    try:
        data["name"] = clean_text(
            page.locator("h1.DUwDvf").first.inner_text(
                timeout=5000
            )
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

    # ---------- City / State ----------
    try:

        if data["address"]:

            parts = [
                p.strip()
                for p in data["address"].split(",")
            ]

            if len(parts) >= 2:
                data["city"] = parts[-2]

            if len(parts) >= 1:

                state = re.sub(
                    r"\d{6}",
                    "",
                    parts[-1]
                )

                data["state"] = state.strip()

    except:
        pass

    return data


# SCROLL SEARCH RESULTS

def scroll_results(page):

    print("Scrolling search results...")

    try:

        panel = page.locator(
            'div[role="feed"]'
        ).first

        previous = 0
        same = 0

        while True:

            panel.evaluate(
                "(el) => el.scrollBy(0, 5000)"
            )

            random_sleep(2, 3)

            cards = page.locator("a.hfpxzc")

            current = cards.count()

            print("Loaded:", current)

            if current == previous:
                same += 1
            else:
                same = 0

            if same >= 3:
                break

            previous = current

    except Exception as e:
        print("Scroll error:", e)


# LOAD QUERIES

def load_queries():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return [
            q.strip()
            for q in f
            if q.strip()
        ]


# SAVE CSV

def save_rows(rows):

    if not rows:
        return

    df = pd.DataFrame(rows)

    df.drop_duplicates(
        subset=["name", "phone"],
        inplace=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )


# MAIN

def main():

    all_rows = []

    # Resume support
    if os.path.exists(OUTPUT_FILE):
        try:
            all_rows = pd.read_csv(
                OUTPUT_FILE
            ).to_dict("records")

            print(
                f"Loaded {len(all_rows)} existing rows"
            )

        except:
            pass

    queries = load_queries()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False,
            slow_mo=500
        )

        context = browser.new_context()

        page = context.new_page()

        page.set_viewport_size({
            "width": 1400,
            "height": 900
        })

        for query in queries:

            print("\n" + "=" * 70)
            print("SEARCH:", query)
            print("=" * 70)

            try:

                search_url = (
                    "https://www.google.com/maps/search/"
                    + query.replace(" ", "+")
                )

                page.goto(
                    search_url,
                    timeout=60000
                )

                random_sleep(6, 8)

                scroll_results(page)

                cards = page.locator(
                    "a.hfpxzc"
                )

                total = cards.count()

                print(
                    f"Businesses found: {total}"
                )

                for i in range(total):

                    try:

                        print(
                            f"\nOpening business {i+1}/{total}"
                        )

                        # Refresh locator every loop
                        cards = page.locator(
                            "a.hfpxzc"
                        )

                        if i >= cards.count():
                            break

                        card = cards.nth(i)

                        card.scroll_into_view_if_needed()

                        random_sleep(1, 2)

                        card.click(force=True)

                        # Wait for panel update
                        page.wait_for_timeout(4000)

                        try:
                            page.wait_for_selector(
                                "h1.DUwDvf",
                                timeout=10000
                            )
                        except:
                            print(
                                "Business panel not loaded"
                            )
                            continue

                        row = extract_business_data(
                            page
                        )

                        row["search_query"] = query

                        # Skip invalid rows
                        if (
                            row["name"] == ""
                            or row["name"] == "Results"
                        ):
                            print(
                                "Skipped invalid row"
                            )
                            continue

                        print(
                            "Name:",
                            row["name"]
                        )

                        all_rows.append(row)

                        save_rows(all_rows)

                        random_sleep(2, 4)

                    except Exception as e:
                        print(
                            f"Business {i+1} failed:",
                            e
                        )

            except Exception as e:
                print("Query failed:", e)

        browser.close()

    print("\nDONE")


if __name__ == "__main__":
    main()
