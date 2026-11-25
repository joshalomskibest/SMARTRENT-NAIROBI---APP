"""The Market report tab of the SmartRent Nairobi app."""
import altair as alt
import pandas as pd
import streamlit as st

# ---------- Colors ----------
# Categorical hues and blue ramp from a validated palette (color-blind safe, readable on
# light and dark pages). Grey stands for "everything else" or "not specified".
CATEGORICAL = ["#338ced", "#e76624", "#00a888", "#d28e05", "#e24d8b"]
NEUTRAL = "#9c9c9c"
BLUE = "#338ced"
RAMP = ["#84b9f3", "#1b64be"]      # light-to-dark blue for ranked bars
LABEL_INK = "#888888"              # readable on both light and dark backgrounds

SECURITY_ORDER = ["Gated+Guard+CCTV", "Gated+Guard", "Guard", "Unknown"]
SECURITY_LABELS = {
    "Gated+Guard+CCTV": "Gated + Guard + CCTV",
    "Gated+Guard": "Gated + Guard",
    "Guard": "Guard only",
    "Unknown": "Not specified",
}
SECURITY_COLORS = {
    "Gated+Guard+CCTV": "#1757ac",
    "Gated+Guard": "#338ced",
    "Guard": "#84b9f3",
    "Unknown": NEUTRAL,
}

OTHER_LABEL = "Other (mixed areas)"
MIN_LISTINGS_FOR_RANKING = 20      # areas with fewer listings are not named "priciest"
BEDROOM_ORDER = ["Studio", "1", "2", "3", "4", "5+"]
AMENITY_ORDER = [str(n) for n in range(7)]
DISTANCE_BINS = [0, 5, 10, 15, 25, 1000]
DISTANCE_ORDER = ["0-5 km", "5-10 km", "10-15 km", "15-25 km", "25+ km"]


# ---------- Small helpers ----------
@st.cache_data
def load_market_data():
    return pd.read_csv("market_data.csv")


def draw(chart):
    """Show a chart. If one chart fails, the rest of the page still works."""
    try:
        st.altair_chart(chart)
    except Exception as error:
        st.warning(f"This chart could not be drawn ({type(error).__name__}).")


def kes(value):
    return f"KSh {value:,.0f}"


def area_name(name):
    return OTHER_LABEL if name == "Other" else name


def bedroom_label(count):
    count = int(count)
    if count == 0:
        return "Studio"
    return "5+" if count >= 5 else str(count)


def area_table(df):
    table = (
        df.groupby("Neighborhood_final")
        .agg(
            Listings=("Price_Ksh", "size"),
            Median_Rent=("Price_Ksh", "median"),
            Median_Distance_km=("Distance_to_CBD_km", "median"),
        )
        .reset_index()
        .rename(columns={"Neighborhood_final": "Neighborhood"})
    )
    table["Area"] = table["Neighborhood"].map(area_name)
    return table


def group_stats(df, key):
    out = (
        df.groupby(key, observed=True)
        .agg(Median_Rent=("Price_Ksh", "median"), Listings=("Price_Ksh", "size"))
        .reset_index()
    )
    out[key] = out[key].astype(str)
    return out


# ---------- Charts ----------
def donut(data, label_col, order_col, colors_by_label):
    labels = data[label_col].tolist()
    colors = [colors_by_label[name] for name in data["Key"]]
    return (
        alt.Chart(data)
        .mark_arc(innerRadius=62, outerRadius=105, padAngle=0.02, cornerRadius=3)
        .encode(
            theta=alt.Theta("Listings:Q", stack=True),
            color=alt.Color(
                f"{label_col}:N",
                scale=alt.Scale(domain=labels, range=colors),
                legend=alt.Legend(title=None, orient="bottom", columns=2, symbolType="circle", labelLimit=240),
            ),
            order=alt.Order(f"{order_col}:Q"),
            tooltip=[
                alt.Tooltip("Name:N", title="Group"),
                alt.Tooltip("Listings:Q", title="Listings", format=","),
                alt.Tooltip("Share:Q", title="Share of listings", format=".1%"),
            ],
        )
        .properties(height=320)
    )


def column_chart(data, key, title, order):
    shared = alt.Chart(data).encode(
        x=alt.X(f"{key}:N", sort=order, title=title, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Median_Rent:Q", title=None, axis=alt.Axis(format="~s")),
        tooltip=[
            alt.Tooltip(f"{key}:N", title=title),
            alt.Tooltip("Median_Rent:Q", title="Typical rent (KSh)", format=",.0f"),
            alt.Tooltip("Listings:Q", title="Listings"),
        ],
    )
    bars = shared.mark_bar(color=BLUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    labels = shared.mark_text(dy=-8, fontSize=12, color=LABEL_INK).encode(
        text=alt.Text("Median_Rent:Q", format=".2s")
    )
    return (bars + labels).properties(height=250)


def market_map(areas):
    data = areas[areas["Neighborhood"] != "Other"]
    x = alt.X(
        "Median_Distance_km:Q",
        title="Typical distance to the city centre (km)",
        scale=alt.Scale(zero=False),
    )
    y = alt.Y(
        "Median_Rent:Q",
        title="Typical monthly rent (KSh)",
        scale=alt.Scale(zero=False),
        axis=alt.Axis(format="~s"),
    )
    bubbles = (
        alt.Chart(data)
        .mark_circle(color=BLUE, opacity=0.7)
        .encode(
            x=x,
            y=y,
            size=alt.Size("Listings:Q", scale=alt.Scale(range=[60, 1600]), legend=None),
            tooltip=[
                alt.Tooltip("Area:N", title="Area"),
                alt.Tooltip("Median_Rent:Q", title="Typical rent (KSh)", format=",.0f"),
                alt.Tooltip("Median_Distance_km:Q", title="Distance (km)", format=".1f"),
                alt.Tooltip("Listings:Q", title="Listings"),
            ],
        )
    )
    names = (
        alt.Chart(data.nlargest(8, "Listings"))
        .mark_text(dy=-16, fontSize=11, color=LABEL_INK)
        .encode(x=x, y=y, text="Area:N")
    )
    return (bubbles + names).properties(height=380)


def league_chart(areas, metric, axis_title):
    ordered = areas.sort_values(metric, ascending=False)
    return (
        alt.Chart(ordered)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X(f"{metric}:Q", title=axis_title, axis=alt.Axis(format="~s")),
            y=alt.Y("Area:N", sort="-x", title=None),
            color=alt.Color(f"{metric}:Q", scale=alt.Scale(range=RAMP), legend=None),
            tooltip=[
                alt.Tooltip("Area:N", title="Area"),
                alt.Tooltip("Median_Rent:Q", title="Typical rent (KSh)", format=",.0f"),
                alt.Tooltip("Listings:Q", title="Listings"),
            ],
        )
        .properties(height=max(120, 24 * len(ordered)))
    )


# ---------- Page sections ----------
def kpi_row(df, areas):
    named = areas[areas["Neighborhood"] != "Other"]
    most_listed = named.sort_values("Listings", ascending=False).iloc[0]
    ranked = named[named["Listings"] >= MIN_LISTINGS_FOR_RANKING]
    if ranked.empty:
        ranked = named
    priciest = ranked.sort_values("Median_Rent", ascending=False).iloc[0]

    share = most_listed["Listings"] / len(df)
    tiles = [
        ("Listings analysed", f"{len(df):,}", "Cleaned Nairobi listings"),
        ("Typical rent", kes(df["Price_Ksh"].median()), "Median monthly rent, all listings"),
        ("Most listed area", most_listed["Area"], f"{most_listed['Listings']:,} listings ({share:.0%})"),
        ("Priciest area", priciest["Area"], f"{kes(priciest['Median_Rent'])} typical"),
    ]
    for column, (label, value, note) in zip(st.columns(4), tiles):
        with column, st.container(border=True):
            st.caption(label)
            st.markdown(f"### {value}")
            st.caption(note)


def takeaways(df, areas):
    lines = []

    none = df[df["Amenity_Count"] == 0]["Price_Ksh"]
    many = df[df["Amenity_Count"] >= 5]["Price_Ksh"]
    if len(none) >= 10 and len(many) >= 10:
        lines.append(
            f"**Amenities:** listings with 5 or more amenities have a typical rent of {kes(many.median())}, "
            f"about {many.median() / none.median():.1f}x the {kes(none.median())} typical for listings with none."
        )

    near = df[df["Distance_to_CBD_km"] < 5]["Price_Ksh"]
    far = df[df["Distance_to_CBD_km"] >= 15]["Price_Ksh"]
    if len(near) >= 10 and len(far) >= 10:
        lines.append(
            f"**Distance:** within 5 km of the centre the typical rent is {kes(near.median())}; "
            f"beyond 15 km it is {kes(far.median())}."
        )

    top = df[df["Security_Level"] == "Gated+Guard+CCTV"]["Price_Ksh"]
    guard = df[df["Security_Level"] == "Guard"]["Price_Ksh"]
    if len(top) >= 10 and len(guard) >= 10:
        lines.append(
            f"**Security:** gated listings with a guard and CCTV have a typical rent of {kes(top.median())}, "
            f"against {kes(guard.median())} for a guard only."
        )

    named = areas[areas["Neighborhood"] != "Other"].sort_values("Listings", ascending=False)
    if len(named) >= 3:
        top3 = named.head(3)
        lines.append(
            f"**Listing volume:** {', '.join(top3['Area'])} together account for "
            f"{top3['Listings'].sum() / len(df):.0%} of all listings."
        )

    if lines:
        with st.container(border=True):
            st.markdown("#### Key takeaways")
            for line in lines:
                st.markdown(f"- {line}")
            st.caption("These are patterns in the listings. They do not prove that one factor causes another.")


def donut_row(df, areas):
    left, right = st.columns(2)

    with left:
        st.markdown("#### Where the listings are")
        named = areas[areas["Neighborhood"] != "Other"].sort_values("Listings", ascending=False)
        top = named.head(5)
        rest = len(df) - top["Listings"].sum()
        rows = [(r["Area"], r["Area"], int(r["Listings"])) for _, r in top.iterrows()]
        rows.append(("All other areas", "All other areas", int(rest)))
        data = pd.DataFrame(rows, columns=["Key", "Name", "Listings"])
        data["Share"] = data["Listings"] / len(df)
        data["Label"] = data.apply(lambda r: f"{r['Name']} · {r['Share']:.0%}", axis=1)
        data["Order"] = range(len(data))
        colors = {name: CATEGORICAL[i] for i, name in enumerate(top["Area"])}
        colors["All other areas"] = NEUTRAL
        draw(donut(data, "Label", "Order", colors))
        st.caption("Share of all listings. Listing volume shows what is on the market, not how many people want to rent.")

    with right:
        st.markdown("#### Security on offer")
        counts = df["Security_Level"].value_counts()
        rows = [
            (level, SECURITY_LABELS[level], int(counts.get(level, 0)))
            for level in SECURITY_ORDER
            if counts.get(level, 0) > 0
        ]
        data = pd.DataFrame(rows, columns=["Key", "Name", "Listings"])
        data["Share"] = data["Listings"] / len(df)
        data["Label"] = data.apply(lambda r: f"{r['Name']} · {r['Share']:.0%}", axis=1)
        data["Order"] = range(len(data))
        draw(donut(data, "Label", "Order", SECURITY_COLORS))
        st.caption("Darker blue means stronger security. Grey means the listing did not say.")


def price_map(areas):
    st.markdown("#### Price map: distance, rent and listing volume")
    draw(market_map(areas))
    st.caption(
        "Each bubble is a neighborhood. Higher means a higher typical rent, further right means further "
        "from the centre, and a bigger bubble means more listings. The mixed \"Other\" group is left out."
    )


def ladders(df):
    st.markdown("#### What moves the rent")
    df = df.dropna(subset=["Distance_to_CBD_km"]).copy()
    df["Bedrooms_Label"] = df["Bedrooms"].map(bedroom_label)
    df["Amenities"] = df["Amenity_Count"].astype(int).astype(str)
    df["Distance_Band"] = pd.cut(
        df["Distance_to_CBD_km"], bins=DISTANCE_BINS, labels=DISTANCE_ORDER, right=False
    ).astype(str)

    first, second, third = st.columns(3)
    with first:
        st.caption("By bedrooms")
        draw(column_chart(group_stats(df, "Bedrooms_Label"), "Bedrooms_Label", "Bedrooms", BEDROOM_ORDER))
    with second:
        st.caption("By number of amenities")
        draw(column_chart(group_stats(df, "Amenities"), "Amenities", "Amenities", AMENITY_ORDER))
    with third:
        st.caption("By distance to the centre")
        draw(column_chart(group_stats(df, "Distance_Band"), "Distance_Band", "Distance", DISTANCE_ORDER))
    st.caption("Typical (median) monthly rent for each group. Hover a bar to see how many listings it is based on.")


def league(areas):
    st.markdown("#### Neighborhood league table")
    controls_left, controls_right = st.columns(2)
    with controls_left:
        view = st.radio("Rank areas by", ["Typical rent", "Number of listings"], horizontal=True)
    with controls_right:
        minimum = st.slider("Hide areas with fewer listings than", 0, 40, 0, step=5)

    shown = areas[areas["Listings"] >= minimum]
    if shown.empty:
        st.info("No areas have that many listings. Lower the slider.")
        return
    if view == "Typical rent":
        draw(league_chart(shown, "Median_Rent", "Typical monthly rent (KSh)"))
    else:
        draw(league_chart(shown, "Listings", "Number of listings"))
    st.caption(
        "Typical means the median across all apartment sizes in that area. Areas with few listings "
        "give less reliable figures, so use the slider to hide them."
    )


def render_market_report():
    df = load_market_data().copy()
    areas = area_table(df)

    st.write("A snapshot of rents across Nairobi and its surroundings, built from the same listings the estimate model learned from.")
    kpi_row(df, areas)
    takeaways(df, areas)
    st.divider()
    donut_row(df, areas)
    st.divider()
    price_map(areas)
    st.divider()
    ladders(df)
    st.divider()
    league(areas)
