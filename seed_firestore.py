import datetime
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-4c737e884f18"

def seed():
    db = firestore.Client(project=PROJECT_ID)
    stations_ref = db.collection("supercharger_stations")

    stations = [
        {
            "id": "sf_embarcadero",
            "name": "San Francisco - Embarcadero",
            "city": "San Francisco",
            "state": "CA",
            "stalls": 16,
            "speed_kw": 250,
            "rates": {
                "off_peak": 0.24, # 11pm - 8am
                "mid_peak": 0.38, # 8am - 12pm, 7pm - 11pm
                "peak": 0.54     # 12pm - 7pm
            },
            "off_peak_hours": "11:00 PM - 8:00 AM",
            "latitude": 37.7955,
            "longitude": -122.3937,
            "address": "4 Embarcadero Center, San Francisco, CA 94111",
            "notes": "Garage parking fees may apply after 2 hours."
        },
        {
            "id": "sf_van_ness",
            "name": "San Francisco - Van Ness Ave",
            "city": "San Francisco",
            "state": "CA",
            "stalls": 20,
            "speed_kw": 250,
            "rates": {
                "off_peak": 0.22, # 10pm - 8am
                "mid_peak": 0.36, # 8am - 1pm, 8pm - 10pm
                "peak": 0.52     # 1pm - 8pm
            },
            "off_peak_hours": "10:00 PM - 8:00 AM",
            "latitude": 37.7845,
            "longitude": -122.4215,
            "address": "1455 Van Ness Ave, San Francisco, CA 94109",
            "notes": "Convenient coffee and grocery stores nearby."
        },
        {
            "id": "daly_city_serramonte",
            "name": "Daly City - Serramonte Center",
            "city": "Daly City",
            "state": "CA",
            "stalls": 24,
            "speed_kw": 250,
            "rates": {
                "off_peak": 0.19, # 11pm - 7am
                "mid_peak": 0.32, # 7am - 2pm, 8pm - 11pm
                "peak": 0.46     # 2pm - 8pm
            },
            "off_peak_hours": "11:00 PM - 7:00 AM",
            "latitude": 37.6685,
            "longitude": -122.4695,
            "address": "3 Serramonte Center, Daly City, CA 94015",
            "notes": "Ample parking, shopping center access."
        },
        {
            "id": "concord_sunvalley",
            "name": "Concord - Sunvalley Mall",
            "city": "Concord",
            "state": "CA",
            "stalls": 12,
            "speed_kw": 250,
            "rates": {
                "off_peak": 0.20, # 10pm - 8am
                "mid_peak": 0.31, # 8am - 3pm, 8pm - 10pm
                "peak": 0.45     # 3pm - 8pm
            },
            "off_peak_hours": "10:00 PM - 8:00 AM",
            "latitude": 37.9701,
            "longitude": -122.0573,
            "address": "1 Sunvalley Mall, Concord, CA 94520",
            "notes": "Located near mall food court."
        },
        {
            "id": "oakland_broadway",
            "name": "Oakland - Broadway Station",
            "city": "Oakland",
            "state": "CA",
            "stalls": 16,
            "speed_kw": 150,
            "rates": {
                "off_peak": 0.21, # 11pm - 8am
                "mid_peak": 0.33, # 8am - 2pm, 7pm - 11pm
                "peak": 0.48     # 2pm - 7pm
            },
            "off_peak_hours": "11:00 PM - 8:00 AM",
            "latitude": 37.8188,
            "longitude": -122.2592,
            "address": "3000 Broadway, Oakland, CA 94611",
            "notes": "V2 chargers (150kW max)."
        }
    ]

    for station in stations:
        doc_id = station["id"]
        stations_ref.document(doc_id).set(station)
        print(f"Seeded station: {station['name']} ({doc_id})")

    print(f"Successfully seeded {len(stations)} stations to Firestore project {PROJECT_ID}!")

if __name__ == "__main__":
    seed()
