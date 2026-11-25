import altair as alt
import pandas as pd
import streamlit as st

# Cross-validated results (5-fold) from the Colab notebook
MODEL_RESULTS = pd.DataFrame({
    "Model": ["Linear Regression", "Random Forest (tuned)", "Gradient Boosting (tuned)"],
    "Typical miss (KSh)": [18379, 17866, 17115],
    "Explained (R²)": [0.715, 0.719, 0.739],
    "Used in app": ["", "", "Yes"],
})

BLUE = "#338ced"
GREY = "#9c9c9c"


def _comparison_chart():
    data = MODEL_RESULTS.copy()
    data["Chosen"] = data["Used in app"].map(lambda v: "Used in this app" if v else "Compared")
    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=4, size=26)
        .encode(
            x=alt.X("Typical miss (KSh):Q", title="Typical miss in KSh (shorter is better)",
                    axis=alt.Axis(format=",.0f"), scale=alt.Scale(domain=[0, 20000])),
            y=alt.Y("Model:N", sort=None, title=None),
            color=alt.Color("Chosen:N", legend=alt.Legend(title=None, orient="bottom"),
                            scale=alt.Scale(domain=["Used in this app", "Compared"],
                                            range=[BLUE, GREY])),
            tooltip=["Model", alt.Tooltip("Typical miss (KSh):Q", format=",.0f"),
                     alt.Tooltip("Explained (R²):Q", format=".3f")],
        )
        .properties(height=150)
    )


def render_about():
    st.write(
        "SmartRent Nairobi estimates a fair monthly rent by learning from real listings. "
        "This page explains how, and how far you can trust it."
    )

    with st.container(border=True):
        st.subheader("How it works")
        st.markdown(
            "1. **Data:** 1,790 apartment listings in Nairobi and its surroundings, cleaned and checked "
            "for impossible values.\n"
            "2. **Learning:** the model looked for patterns linking rent to size, bedrooms, bathrooms, "
            "building age, amenities, security, distance to the city centre and neighborhood.\n"
            "3. **Estimate:** when you press the button, your answers go through the same patterns "
            "and the model returns a rent."
        )

    with st.container(border=True):
        st.subheader("Why Gradient Boosting")
        st.write(
            "Three models were trained on the same data and judged on listings they had not seen "
            "(5-fold cross-validation). Gradient Boosting, built from many small decision trees that "
            "each correct the mistakes of the last, missed by the least."
        )
        st.altair_chart(_comparison_chart())
        st.dataframe(MODEL_RESULTS.drop(columns="Used in app"), hide_index=True)
        st.caption(
            "Typical miss is the average gap between estimate and real rent. R² is the share of the "
            "variation in rents the model explains (1.0 would be perfect). The three models are "
            "close, so the gain is real but modest."
        )

    with st.container(border=True):
        st.subheader("What to keep in mind")
        st.markdown(
            "- **It is an estimate, not a valuation.** Half of real rents fell within about 15% "
            "of the estimate, and three quarters within about 26%.\n"
            "- **Condition and finish are invisible.** The model cannot see repairs, view, noise, "
            "or how well the building is managed.\n"
            "- **Amenities are counted, not weighed.** A pool and a playground count the same.\n"
            "- **Size is partly filled in.** Many listings did not state size, so it was estimated "
            "from the number of bedrooms.\n"
            "- **Distance is typical for the area.** It comes from the neighborhood, not your exact address.\n"
            "- **Listings are asking rents.** Final agreed rents are often lower.\n"
            "- **Small areas are less reliable.** Neighborhoods with few listings, and the \"Other\" group, "
            "carry more uncertainty."
        )

    with st.container(border=True):
        st.subheader("About this project")
        st.write(
            "SmartRent Nairobi is a final year project by Joshua Shallom, BSc Business and IT, "
            "Dedan Kimathi University of Technology. Data: Nairobi apartment listings dataset from Kaggle."
        )
        st.caption(
            "For guidance only. Do not treat the estimate as financial or legal advice. "
            "Always view a property and confirm terms before paying a deposit."
        )
