import json

import altair as alt
import joblib
import pandas as pd
import streamlit as st

st.set_page_config(page_title="SmartRent Nairobi", layout="centered")


# ---------- Load the saved model and lookups (runs once) ----------
@st.cache_resource
def load_artifacts():
    model = joblib.load("smartrent_gb_model.joblib")
    columns = joblib.load("model_columns.joblib")
    distance_lookup = joblib.load("neighborhood_distance.joblib")
    return model, columns, distance_lookup


model, model_columns, distance_lookup = load_artifacts()


@st.cache_data
def load_importance():
    return pd.read_csv("feature_importance.csv")


@st.cache_data
def load_neighborhood_stats():
    return pd.read_csv("neighborhood_stats.csv")


@st.cache_data
def load_error_profile():
    # Cross-validated error of the final model: {"mae": ..., "median_ape": ..., "p75_ape": ...}
    with open("model_error.json") as f:
        return json.load(f)


# ---------- Options shown to the user ----------
AMENITIES = [
    "Gym",
    "Swimming pool",
    "Lift / elevator",
    "Backup generator",
    "Children's playground",
    "Dedicated parking",
]

# Label shown to the user -> category name the model was trained on
SECURITY_OPTIONS = {
    "Not specified": "Unknown",
    "Guard only": "Guard",
    "Gated + Guard": "Gated+Guard",
    "Gated + Guard + CCTV": "Gated+Guard+CCTV",
}

OTHER_LABEL = "Other (area not listed)"

error_profile = load_error_profile()
TYPICAL_ERROR = round(error_profile["mae"], -2)   # typical miss, in KSh
FAIR_BAND = error_profile["median_ape"]           # half of estimates are within this % of the real rent
CLEAR_BAND = error_profile["p75_ape"]             # three quarters are within this %


def judge_price(asking, predicted):
    """Return (verdict, strength, difference) comparing an asking rent with the estimate.

    verdict: "good", "fair" or "high"; strength: "clearly" beyond the wider band, else "".
    """
    difference = (asking - predicted) / predicted
    if abs(difference) <= FAIR_BAND:
        return "fair", "", difference
    strength = "clearly" if abs(difference) > CLEAR_BAND else ""
    return ("good" if difference < 0 else "high"), strength, difference

named_areas = sorted(n for n in distance_lookup if n != "Other")
neighborhood_options = named_areas + (["Other"] if "Other" in distance_lookup else [])


def neighborhood_label(name):
    return OTHER_LABEL if name == "Other" else name


# ---------- Turn the user's answers into the 31 columns the model expects ----------
def build_input(sq_mtrs, bedrooms, bathrooms, age, amenity_count,
                distance, neighborhood, security):
    row = pd.DataFrame(0.0, index=[0], columns=model_columns)

    numeric_values = {
        "sq_mtrs": sq_mtrs,
        "Bedrooms": bedrooms,
        "Bathrooms": bathrooms,
        "Building_Age_Years": age,
        "Amenity_Count": amenity_count,
        "Distance_to_CBD_km": distance,
    }
    for column, value in numeric_values.items():
        row.at[0, column] = float(value)

    # One-hot columns. The two baseline categories (Brookside and Gated+Guard)
    # have no column of their own, so for them every column stays 0.
    for column in (f"Neighborhood_final_{neighborhood}", f"Security_Level_{security}"):
        if column in row.columns:
            row.at[0, column] = 1.0

    return row


# ---------- The page ----------
st.title("SmartRent Nairobi")
st.write("Estimate the monthly rent of an apartment in Nairobi and its surroundings.")

left, right = st.columns(2)

with left:
    neighborhood = st.selectbox(
        "Neighborhood", neighborhood_options, format_func=neighborhood_label
    )
    bedrooms = st.number_input("Bedrooms (0 = studio)", min_value=0, max_value=6, value=2, step=1)
    bathrooms = st.number_input("Bathrooms", min_value=1, max_value=6, value=2, step=1)
    sq_mtrs = st.number_input("Size (sq m)", min_value=15, max_value=418, value=120, step=5)

with right:
    security_label = st.selectbox("Security", list(SECURITY_OPTIONS.keys()), index=2)
    age = st.number_input("Building age (years)", min_value=0, max_value=33, value=5, step=1)
    amenities = st.multiselect(
        "Amenities",
        AMENITIES,
        help="Tick everything the building offers. The estimate uses how many you select.",
    )
    asking_rent = st.number_input(
        "Asking rent in KSh (optional)", min_value=0, value=0, step=1000
    )

distance = float(distance_lookup[neighborhood])
st.caption(
    f"Distance to the city centre is estimated at {distance:.1f} km, "
    "which is typical for this area."
)

if st.button("Estimate rent", type="primary"):
    row = build_input(
        sq_mtrs, bedrooms, bathrooms, age, len(amenities),
        distance, neighborhood, SECURITY_OPTIONS[security_label],
    )
    predicted = float(model.predict(row)[0])

    low = predicted * (1 - FAIR_BAND)
    high = predicted * (1 + FAIR_BAND)

    st.subheader(f"Estimated rent: KSh {predicted:,.0f} per month")
    st.write(f"Likely range: KSh {low:,.0f} to KSh {high:,.0f}")
    st.caption(
        f"In testing, estimates were typically off by about KSh {TYPICAL_ERROR:,}. "
        "The range is where about half of real rents fell in testing."
    )

    if asking_rent > 0 and predicted > 0:
        verdict, strength, difference = judge_price(asking_rent, predicted)
        size = f"{abs(difference):.0%}"

        if verdict == "fair":
            st.info(f"Fair price. The asking rent is within the likely range ({difference:+.0%} from the estimate).")
        elif verdict == "good":
            title = "Clearly a good deal" if strength else "Good deal"
            st.success(
                f"{title}. The asking rent is {size} below the estimate. "
                "Check why it is lower: the model cannot see the condition of the building "
                "or features outside the form."
            )
        else:
            title = "Clearly overpriced" if strength else "Overpriced"
            st.warning(
                f"{title}. The asking rent is {size} above the estimate. "
                "It may be worth negotiating, or asking what extra the landlord is offering."
            )

        # Where the asking rent sits compared with the estimate and its likely range
        axis_min = min(low, asking_rent) * 0.85
        axis_max = max(high, asking_rent) * 1.15
        scale = alt.Scale(domain=[axis_min, axis_max])
        x_axis = alt.Axis(format=",.0f", title="Monthly rent (KSh)")

        band = (
            alt.Chart(pd.DataFrame({"low": [low], "high": [high]}))
            .mark_rect(opacity=0.3, color="steelblue")
            .encode(x=alt.X("low:Q", scale=scale, axis=x_axis), x2="high:Q")
        )
        estimate_line = (
            alt.Chart(pd.DataFrame({"rent": [predicted]}))
            .mark_rule(color="steelblue", strokeWidth=3)
            .encode(x=alt.X("rent:Q", scale=scale))
        )
        asking_line = (
            alt.Chart(pd.DataFrame({"rent": [float(asking_rent)]}))
            .mark_rule(color="crimson", strokeWidth=3)
            .encode(x=alt.X("rent:Q", scale=scale))
        )
        st.altair_chart((band + estimate_line + asking_line).properties(height=90))
        st.caption("Blue line: estimate. Shaded band: likely range. Red line: the asking rent.")

# ---------- Compare neighborhoods ----------
LOW_DATA_THRESHOLD = 20  # areas with fewer listings than this get a caution note

with st.expander("Compare neighborhoods"):
    stats = load_neighborhood_stats()
    available = [n for n in neighborhood_options if n in set(stats["Neighborhood"])]

    chosen = st.multiselect(
        "Pick two or three neighborhoods to compare",
        available,
        default=[neighborhood] if neighborhood in available else [],
        max_selections=3,
        format_func=neighborhood_label,
    )

    if len(chosen) < 2:
        st.info("Pick at least two neighborhoods to see the comparison.")
    else:
        picked = stats[stats["Neighborhood"].isin(chosen)].copy()
        picked["Area"] = picked["Neighborhood"].map(neighborhood_label)

        rent_chart = (
            alt.Chart(picked)
            .mark_bar()
            .encode(
                x=alt.X("Median_Rent:Q", title="Typical monthly rent (KSh)", axis=alt.Axis(format=",.0f")),
                y=alt.Y("Area:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("Area:N"),
                    alt.Tooltip("Median_Rent:Q", title="Typical rent (KSh)", format=",.0f"),
                    alt.Tooltip("Listings:Q", title="Listings"),
                ],
            )
        )
        st.altair_chart(rent_chart)

        table = pd.DataFrame({
            "Neighborhood": picked["Area"],
            "Typical rent (KSh)": picked["Median_Rent"].map(lambda v: f"{v:,.0f}"),
            "Typical bedrooms": picked["Median_Bedrooms"].map(lambda v: f"{v:g}"),
            "Distance to centre (km)": picked["Median_Distance_km"].map(lambda v: f"{v:.1f}"),
            "Listings": picked["Listings"],
        }).sort_values("Listings", ascending=False)
        st.dataframe(table, hide_index=True)

        thin = picked.loc[picked["Listings"] < LOW_DATA_THRESHOLD, "Area"].tolist()
        if thin:
            st.warning(
                "Fewer than " + str(LOW_DATA_THRESHOLD) + " listings for: " + ", ".join(thin)
                + ". Treat their figures with extra caution."
            )

        st.caption(
            "Typical means the median across all apartment sizes in that area, so areas with larger "
            "apartments look more expensive. The \"Other\" group mixes many smaller areas."
        )

# ---------- What drives the estimate ----------
with st.expander("What drives the estimate?"):
    importance = load_importance()
    chart = (
        alt.Chart(importance)
        .mark_bar()
        .encode(
            x=alt.X("Importance:Q", title="Share of the model's decision", axis=alt.Axis(format="%")),
            y=alt.Y("Feature:N", sort="-x", title=None),
            tooltip=["Feature", alt.Tooltip("Importance:Q", format=".1%")],
        )
    )
    st.altair_chart(chart)
    st.caption(
        "This shows how much the model relied on each factor when it learned from 1,790 listings. "
        "It does not show whether a factor raises or lowers the rent. "
        "Amenities, distance to the city centre and security level matter most."
    )


st.divider()
st.caption(
    "This estimate comes from a machine learning model trained on 1,790 Nairobi listings. "
    "The model was trained on a count of amenities per listing, so each amenity you tick "
    "counts equally. Real rents vary."
)
