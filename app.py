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
TYPICAL_ERROR = 17000  # cross-validated MAE of the final model, rounded

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

    st.subheader(f"Estimated rent: KSh {predicted:,.0f} per month")
    st.caption(
        f"In testing, estimates were typically off by about KSh {TYPICAL_ERROR:,}."
    )

    if asking_rent > 0 and predicted > 0:
        difference = (asking_rent - predicted) / predicted
        if difference > 0.10:
            st.warning(
                f"The asking rent is {difference:.0%} above the estimate for similar apartments."
            )
        elif difference < -0.10:
            st.success(
                f"The asking rent is {abs(difference):.0%} below the estimate for similar apartments. "
                "This could be a good deal."
            )
        else:
            st.info("The asking rent is close to the estimate for similar apartments.")

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
