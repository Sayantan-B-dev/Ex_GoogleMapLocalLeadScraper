cities = [
    "Mumbai",
    "Delhi",
    "Gurugram",
    "Noida",
    "Bengaluru",
    "Hyderabad",
    "Pune",
    "Kolkata",
    "Ahmedabad",
    "Goa",
    "Lonavala",
    "Lucknow",
    "Indore",
    "Bhopal",
    "Bhubaneswar",
    "Patna",
    "Nagpur",
    "Surat",
    "Vapi",
    "Vadodara",
    "Raipur",
    "Bilaspur",
    "Udaipur",
    "Jaipur",
    "Jodhpur",
    "Bikaner",
    "Siliguri"
]

categories = [
    "Event Management Company",
    "Event Planner",
    "Event Organizer",
    "Event Agency",
    "Corporate Event Planner",
    "Corporate Event Management Company",
    "Wedding Planner",
    "Wedding Management Company",
    "Wedding Organizer",
    "Destination Wedding Planner",
    "Wedding Decorator",
    "Wedding Designer",
    "Event Production Company",
    "Artist Management Company",
    "Entertainment Agency",
    "Talent Agency"
]

# Generate all search queries
queries = []

for city in cities:
    for category in categories:
        queries.append(f"{city} {category}")

# Export to a .txt file
with open("google_maps_queries.txt", "w", encoding="utf-8") as f:
    for query in queries:
        f.write(query + "\n")

print(f"Saved {len(queries)} queries to google_maps_queries.txt")