import trino
import traceback

# -----------------------------
# Replace these with your API client credentials
# -----------------------------
API_CLIENT_USER = "ms68672-api-client"  # e.g., ms68672-api-client
API_CLIENT_KEY  = "DSVFGaCtVHvVXGcniVX8H58SmX9oRv21"             # the API key provided by OpenSky

try:
    # -----------------------------
    # Connect to OpenSky Trino
    # -----------------------------
    conn = trino.dbapi.connect(
        host="trino.opensky-network.org",
        port=443,
        user=API_CLIENT_USER,
        http_scheme="https",
        catalog="opensky",
        schema="default",
        auth=trino.auth.BasicAuthentication(API_CLIENT_USER, API_CLIENT_KEY)
    )

    cursor = conn.cursor()

    # -----------------------------
    # Test query
    # -----------------------------
    cursor.execute("SELECT COUNT(*) FROM state_vectors_data4 LIMIT 1")
    result = cursor.fetchall()
    print("Connection successful! Query result:", result)

except trino.exceptions.DatabaseError as e:
    print("Trino DatabaseError:", e)
    traceback.print_exc()

except Exception as e:
    print("Other error:", e)
    traceback.print_exc()