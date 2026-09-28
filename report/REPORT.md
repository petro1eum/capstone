# Where to open a café in central Moscow?

*Applied Data Science Capstone (IBM / Coursera): the Battle of the Neighbourhoods, Moscow edition.*
The analysis behind this report is
[`notebooks/03_cafe_location_analysis.ipynb`](../notebooks/03_cafe_location_analysis.ipynb);
a Russian version is in [`REPORT.ru.md`](REPORT.ru.md).

![Opportunity map 2026: red cells have fewer cafés and restaurants than their surroundings would support; numbers mark the 2026 shortlist](figures/map_screenshot.jpg)

*Opportunity map for 2026; the [interactive version](cafe_opportunity_map.html), with the 2019
layers too, opens in a browser once downloaded. Map tiles © OpenStreetMap contributors.*

## 1. Introduction: the business problem

Central Moscow is one of the densest café markets in Europe: within 6 km of Red Square the city
register listed almost 4,000 cafés and restaurants in 2019. Opening one more café there is mostly a
bet on the location. A good site sits on a steady flow of people (commuters coming out of the
metro, shoppers, visitors of hairdressers and repair shops, students) but is not already crowded
with competitors that absorb that flow.

**Stakeholder.** An entrepreneur or a franchise developer who plans a new café (coffee, pastries,
light meals) in central Moscow and needs a short list of places worth a field visit and a rent
search.

**Question.** Which locations within 6 km of Red Square have the footfall generators that usually
support many cafés, yet host noticeably fewer cafés and restaurants than comparable places?

The project was started in 2019 and finished in 2026, which allows one more question: did the
places found under-served in 2019 fill up since?

## 2. Data

| Layer | Source | Records | Used as |
|---|---|---:|---|
| Candidate locations | Hexagonal grid within 6 km of Red Square, 600 m step | 364 | units of analysis |
| Catering register | [data.mos.ru](https://data.mos.ru), 2019: type, seats, chain flag | 15,366 | competitors: *кафе* and *ресторан* |
| Metro entrances and exits | data.mos.ru, 2019 | 1,067 | exits within 300 m, distance to the nearest exit |
| Surface transport stops | data.mos.ru, 2019 | 11,507 | stops within 300 m |
| Paid street parking | data.mos.ru, 2019 | 9,254 zones | parking spaces within 300 m |
| Shopping register | data.mos.ru, 2019 | 60,320 | shops within 300 m |
| Consumer services | data.mos.ru, 2019 | 14,540 | services within 300 m |
| Fitness | data.mos.ru, 2019 | 385 facilities | gyms within 300 m |
| Universities and colleges | [OpenStreetMap](https://www.openstreetmap.org/copyright), 28 September 2026 | 283 | universities within 300 m |
| Cafés, restaurants, fast food, bars | OpenStreetMap, 28 September 2026 | 6,729 | the check against 2026 and the 2026 shortlist |

The grid and the Moscow Open Data layers were collected in 2019
([notebook 01](../notebooks/01_data_collection_moscow_open_data.ipynb)). The catering and shopping
registers were restored in 2026 from a backup of the project's Dropbox (`data/dropbox_2019/`).
Following the 2019 definition, the **competitors are the *кафе* and *ресторан* types of the
catering register**; fast food, bars, canteens and buffets are described but not counted. The 2019
education register lists mostly schools of the city education department (534 of 620) and no
federal universities, so universities and colleges come from OpenStreetMap. The cinema register (14 municipal cinemas) is
too sparse to use. Details and the data fixes are in [`data/README.md`](../data/README.md).

## 3. Methodology

1. **Projection.** All coordinates are projected to UTM zone 37N (EPSG:32637). The 2019 notebook
   used zone 33, whose central meridian is 22.6° west of Moscow; it overstated distances by 2.4%.
2. **Features.** For each candidate cell, the number of objects of every layer within 300 m (about
   four minutes on foot), the parking capacity within 300 m, and the distances to the nearest metro
   exit and to Red Square.
3. **Exploratory analysis.** Catering composition, chains, and Spearman correlations between
   competitor density and each footfall generator.
4. **Neighbourhood typology.** k-means on standardised features (log counts, distances in km),
   k = 4 chosen from the inertia curve and interpretability.
5. **Demand model.** A Poisson GLM predicts the number of competitors from the footfall generators
   only: `log(1 + count)` features capped at the 99th percentile, and linear distances. Gradient
   boosting with a Poisson loss serves as a flexible benchmark. Models are compared with **spatial
   cross-validation**: cells are grouped into 2 × 2 km blocks and the 38 blocks are dealt at random
   into 6 folds, so no cell is predicted by a model that saw its neighbours. The GLM's out-of-fold
   prediction is the expected number of competitors; its effects get 95% intervals from a block
   bootstrap (300 resamples).
6. **Opportunity score.** The standardised gap between the actual and the expected number of
   competitors, with a negative binomial variance (`expected + expected² / θ`) because the counts
   are overdispersed. The pipeline is run with 250, 300 and 400 m catchments and the three gaps are
   averaged, so the result does not hinge on one catchment size.
7. **Shortlist.** Eligible cells have, for at least two of the three catchments, a metro exit within
   500 m, at least 10 shops and services around them and at least the median expected demand. They
   are ranked by the opportunity score, most under-served first.
8. **Check against 2026.** OpenStreetMap shows where cafés and restaurants are in 2026. If the
   expectation captures demand, the cells under-served in 2019 should have gained venues since. The
   test controls for regression to the mean with a least-squares fit of the log change on the 2019
   count and the 2019 expectation (block bootstrap, 1,000 resamples), and for the shocks of
   2020-2026 with the distance to Red Square and the type of place.
9. **The 2026 shortlist.** The same pipeline with the cafés and restaurants of 2026 as competitors.

## 4. Results

### The market in 2019

Within 6 km of Red Square the register lists 5,784 catering venues: 2,747 cafés, 1,209
restaurants, 547 canteens, 450 bars, 448 quick-service outlets and snack bars, and 383 buffets,
cafeterias and cookery counters. The 3,956 cafés and restaurants, with 233,000 seats, are the
competitors. 22% of them carry the register's chain flag; the largest chains sell coffee.

![Largest chains](figures/fig1_top_chains.png)

![Competitors per cell](figures/fig2_competitors_map.png)

### What goes together with cafés

![Spearman correlations](figures/fig3_correlations.png)

Competitor density rises with shops and consumer services (ρ = 0.73 for both), parking spaces
(0.47) and metro exits (0.40), and falls with the distance to the metro (−0.53) and to Red Square
(−0.56).

### Four types of places

![Typology map](figures/fig5_typology_map.png)

| Type | Cells | Cafés and restaurants | Metro exits | Shops | Services | Nearest metro, m | From Red Square, km |
|---|---:|---:|---:|---:|---:|---:|---:|
| Transit hubs | 45 | 26 | 4 | 60 | 15 | 138 | 3.3 |
| Central neighbourhoods | 76 | 15 | 0 | 22 | 12 | 438 | 2.5 |
| Residential belt | 157 | 4 | 0 | 12 | 5 | 573 | 4.3 |
| Parks, rail and industrial land | 86 | 0 | 0 | 1 | 0 | 773 | 5.1 |

*Medians within 300 m of the cells of each type. The silhouette score is low for every k (0.17 for
k = 4), as usual for gradually changing urban fabric; the selection plots are in the notebook.*

### The demand model

| Model | D², spatial CV |
|---|---:|
| Poisson GLM, log distances | 0.62 |
| **Poisson GLM, linear distances** | **0.67** |
| Gradient boosting, Poisson loss | 0.63 |
| Average of the GLM and boosting | 0.67 |

Distances work better linearly (an exponential decay of density, the classic urban density
gradient) than as logarithms, which explode next to Red Square. Boosting does not beat the GLM and
averaging the two adds nothing, so the interpretable GLM gives the expected counts. The footfall
generators explain two thirds of the Poisson deviance of competitor counts; the rest is what the
data does not see. An ordinary random split scores the GLM almost the same (0.66).

![Model effects](figures/fig6_model_effects.png)

| Change | Expected cafés and restaurants | 95% interval |
|---|---:|---|
| 1 km farther from Red Square | −22% | −28% … −17% |
| 100 m farther from the nearest metro exit | −4.5% | −6.9% … −2.0% |
| Twice as many shops | +26% | +21% … +30% |
| Twice as many consumer services | +18% | +9% … +30% |
| Twice as many metro exits | +8% | +0.3% … +16% |
| Twice the parking spaces, bus stops, universities or gyms | not distinguishable from zero | |

### The 2019 shortlist

117 of the 364 cells are eligible. The counts are strongly overdispersed (Pearson dispersion 5.5,
negative binomial θ = 4.0), hence the negative binomial standardisation. Counts and expectations
are for the 300 m catchment; addresses are the nearest OpenStreetMap address points.

![Actual vs expected](figures/fig7_expected_vs_actual.png)

![Opportunity map 2019](figures/fig8_opportunity_map_2019.png)

| # | Nearest metro | Address of the cell centre | Metro exit, m | From Red Square, km | Cafés and restaurants, 2019 | Expected | Score | In OpenStreetMap 2026 |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Proletarskaya | [Stroykovskaya Street, 10](https://www.openstreetmap.org/?mlat=55.733882&mlon=37.673428#map=17/55.733882/37.673428) | 366 | 3.9 | 1 | 9.8 | −1.53 | 7 |
| 2 | Maryina Roshcha | [Sheremetyevskaya Street, 8](https://www.openstreetmap.org/?mlat=55.797583&mlon=37.618591#map=17/55.797583/37.618591) | 114 | 4.9 | 4 | 18.2 | −1.40 | 7 |
| 3 | Taganskaya | [Goncharnaya Embankment, 3](https://www.openstreetmap.org/?mlat=55.739033&mlon=37.646976#map=17/55.739033/37.646976) | 377 | 2.3 | 2 | 14.9 | −1.27 | 7 |
| 4 | Proletarskaya | [Krestyanskaya Square, 10](https://www.openstreetmap.org/?mlat=55.73215&mlon=37.657568#map=17/55.73215/37.657568) | 411 | 3.3 | 1 | 7.8 | −1.27 | 2 |
| 5 | Leninsky Prospekt | [Leninsky Avenue, 39A](https://www.openstreetmap.org/?mlat=55.707955&mlon=37.583639#map=17/55.707955/37.583639) | 138 | 5.6 | 1 | 8.5 | −1.24 | 5 |
| 6 | Rizhskaya | [Prospekt Mira, 88](https://www.openstreetmap.org/?mlat=55.794151&mlon=37.636257#map=17/55.794151/37.636257) | 171 | 4.6 | 2 | 8.2 | −1.21 | 0 |
| 7 | Shabolovskaya | [Shukhova Street, 14](https://www.openstreetmap.org/?mlat=55.716606&mlon=37.613556#map=17/55.716606/37.613556) | 417 | 4.2 | 3 | 10.3 | −1.20 | 4 |
| 8 | Ulitsa 1905 Goda | [Bolshaya Dekabrskaya Street, 11](https://www.openstreetmap.org/?mlat=55.766493&mlon=37.555163#map=17/55.766493/37.555163) | 326 | 4.4 | 5 | 15.8 | −1.18 | 7 |
| 9 | Proletarskaya | [Krutitsky Val Street, 3](https://www.openstreetmap.org/?mlat=55.730433&mlon=37.666384#map=17/55.730433/37.666384) | 134 | 3.8 | 9 | 24.6 | −1.15 | 9 |
| 10 | Komsomolskaya | [Komsomolskaya Square, 4](https://www.openstreetmap.org/?mlat=55.775217&mlon=37.659244#map=17/55.775217/37.659244) | 167 | 3.4 | 8 | 26.2 | −1.15 | 21 |

### Seven years later

![Change 2019 to 2026 by quintile of the 2019 score](figures/fig9_look_forward.png)

The two sources count almost the same number of cafés and restaurants around the grid cells (3,659
in the 2019 register, 3,691 in OpenStreetMap 2026), so the check compares changes across cells.
The fifth of the cells that were most under-served in 2019 had 69% more venues in 2026; the most
saturated fifth had 11% fewer.

| 2019 opportunity score | Cells | Venues 2019 | Venues 2026 | Change |
|---|---:|---:|---:|---:|
| 1: most under-served | 74 | 130 | 220 | ×1.69 |
| 2 | 73 | 337 | 431 | ×1.28 |
| 3 | 74 | 635 | 686 | ×1.08 |
| 4 | 70 | 1,046 | 1,004 | ×0.96 |
| 5: most saturated | 73 | 1,511 | 1,350 | ×0.89 |

Part of this is regression to the mean: a count that is unusually low in one source tends to be
higher in another. At equal 2019 counts, twice the expected count meant about 10% more venues by
2026 (95% interval +1% to +19%). Eight of the ten cells of the 2019 shortlist gained venues, and
together they went from 36 to 69.

### The market, or the years 2020-2026?

The seven years between the sources were not ordinary ones. The pandemic and remote work, the war
and the sanctions, the exit of foreign chains (Starbucks, McDonald's and KFC reopened under new
names) and the collapse of foreign tourism moved demand between kinds of places on their own. Three
checks separate them from the model:

- Beyond 3 km from Red Square (268 cells) the pattern is the same: ×1.62 in the most under-served
  fifth, ×0.83 in the most saturated. It is not only the tourist centre emptying out.
- With the distance to Red Square in the fit, the effect of the expectation shrinks to +4% (95%
  interval −5% to +13%) and cannot be told from zero. The model's own share is hard to separate
  from location.
- The change follows the type of place: transit hubs lost 12% of their venues (the streets around
  the Kremlin, the Expocentre, big shopping malls), the residential belt gained 11%, parks and
  former industrial land doubled from a low base. OpenStreetMap also maps venues inside malls and
  exhibition halls less completely than the register did, which adds to the losses of the hubs.

| Type of place | Cells | Venues 2019 | Venues 2026 | Change |
|---|---:|---:|---:|---:|
| Transit hubs | 45 | 1,284 | 1,126 | ×0.88 |
| Central neighbourhoods | 76 | 1,430 | 1,428 | ×1.00 |
| Residential belt | 157 | 847 | 936 | ×1.11 |
| Parks, rail and industrial land | 86 | 98 | 201 | ×2.05 |

The check agrees with the model in direction but does not prove it, because the shocks of these
years moved the market the same way.

### The 2026 shortlist

With the competitors of 2026 the model explains 58% of the deviance (OpenStreetMap is a noisier
source than the register) and 117 cells are eligible again. The last column gives the count of the
2019 register for comparison.

![Opportunity map 2026](figures/fig10_opportunity_map_2026.png)

| # | Nearest metro | Address of the cell centre | Metro exit, m | From Red Square, km | Cafés and restaurants, 2026 | Expected | Score | In the 2019 register |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Savyolovskaya | [Sushchyovsky Val Street, 9](https://www.openstreetmap.org/?mlat=55.792391&mlon=37.595654#map=17/55.792391/37.595654) | 376 | 4.6 | 1 | 17.4 | −1.56 | 9 |
| 2 | Rizhskaya | [Prospekt Mira, 88](https://www.openstreetmap.org/?mlat=55.794151&mlon=37.636257#map=17/55.794151/37.636257) | 171 | 4.6 | 0 | 9.4 | −1.55 | 2 |
| 3 | Maryina Roshcha | [Sushchyovsky Val Street, 56](https://www.openstreetmap.org/?mlat=55.792416&mlon=37.620372#map=17/55.792416/37.620372) | 253 | 4.3 | 1 | 10.7 | −1.48 | 3 |
| 4 | Kutuzovskaya | [Kutuzovsky Avenue, 35](https://www.openstreetmap.org/?mlat=55.740622&mlon=37.539417#map=17/55.740622/37.539417) | 321 | 5.3 | 1 | 7.5 | −1.36 | 2 |
| 5 | Begovaya | [Khoroshyovskoye Highway, 1](https://www.openstreetmap.org/?mlat=55.773369&mlon=37.544541#map=17/55.773369/37.544541) | 4 | 5.3 | 4 | 13.6 | −1.35 | 8 |
| 6 | Ploshchad Ilyicha | [Rogozhsky Val Street, 9/2](https://www.openstreetmap.org/?mlat=55.742498&mlon=37.678702#map=17/55.742498/37.678702) | 439 | 3.8 | 4 | 15.7 | −1.29 | 8 |
| 7 | Krasnopresnenskaya | [Druzhinnikovskaya Street, 11A](https://www.openstreetmap.org/?mlat=55.757906&mlon=37.574609#map=17/55.757906/37.574609) | 303 | 3.0 | 3 | 11.1 | −1.26 | 4 |
| 8 | Dubrovka | [Sharikopodshipnikovskaya Street, 13](https://www.openstreetmap.org/?mlat=55.718383&mlon=37.678742#map=17/55.718383/37.678742) | 118 | 5.3 | 4 | 16.3 | −1.26 | 16 |
| 9 | Proletarskaya | [Krestyanskaya Square, 10](https://www.openstreetmap.org/?mlat=55.73215&mlon=37.657568#map=17/55.73215/37.657568) | 411 | 3.3 | 2 | 9.5 | −1.17 | 1 |
| 10 | Krasnoselskaya | [Verkhnyaya Krasnoselskaya Street, 15b](https://www.openstreetmap.org/?mlat=55.783833&mlon=37.664522#map=17/55.783833/37.664522) | 440 | 4.3 | 3 | 11.6 | −1.13 | 13 |

All cells with their features and both years' scores: [`cell_scores.csv`](cell_scores.csv); the
shortlists: [`shortlist_2019.csv`](shortlist_2019.csv) and [`shortlist_2026.csv`](shortlist_2026.csv).

**Robustness.** #1 Savyolovskaya, #3 Maryina Roshcha, #5 Begovaya, #6 Ploshchad Ilyicha and
#7 Krasnopresnenskaya are eligible with every catchment, rank in the top 12 with each of them, stay
in the top 10 when fast food counts as competition too, and were under-served in the 2019 register
as well.

## 5. Discussion

**Gaps tend to close, and the model is not the only reason.** The under-served cells of 2019 gained
venues and the saturated ones lost some, also outside the historic centre. Yet the pandemic, remote
work, the war and sanctions, the exit of foreign chains and the collapse of foreign tourism moved
cafés away from transit hubs and towards residential streets on their own, the same direction the
model points to. What the check does show is that gaps do not stay open for long, so the shortlist
has to be rebuilt on fresh data and acted on quickly.

**The historic core is taken.** No 2026 candidate lies inside the Garden Ring: the centre has as
many cafés as its footfall generators suggest, or more. The only such cell on the 2019 list,
Goncharnaya Embankment by Taganskaya, has gained five venues since. The 2026 candidates are
3.0-5.3 km from Red Square, around the Third Ring Road, within 440 m of a metro exit.

**Check the counts before the visit.** OpenStreetMap misses venues, most often inside markets and
malls, so where it counts far fewer cafés and restaurants than the 2019 register did, part of the
gap may be missing data:

- #1 Savyolovskaya: 9 venues in the register, all in the Savyolovsky market complex
  (Sushchyovsky Val, 5), and 1 in OpenStreetMap. It stays a candidate because it was under-served in
  2019 too, with 9 venues where 25 were expected.
- #8 Dubrovka: 16 in the register and 4 in OpenStreetMap, which tags 10 venues around the market as
  fast food; the cell leaves the top 10 once fast food counts.
- #10 Krasnoselskaya: 13 in the register, 11 of them at one address, Verkhnyaya Krasnoselskaya 3A
  (a food court, judging by the names), and 3 in OpenStreetMap. The cell had as many venues as
  expected in 2019, which makes it the weakest entry.

**What the model does not see.** The cells with the largest surplus of competitors in 2019 are the
Depo food mall on Lesnaya Street near Belorusskaya (41 venues where 6 are expected; the register
lists its counters as some thirty *Веранда* restaurants), some thirty small cafés at one address on
Nizhnyaya Krasnoselskaya Street near Baumanskaya, the Moscow City towers, the Hotel Ukraina with the
Trekhgornaya Manufaktura business quarter, and the World Trade Center. Food halls, offices and
hotels draw far more cafés than shops and metro exits predict, and the same blind spot can make a
place look under-served when its demand comes from something the data does not hold.

**Limitations.**

- The 2019 analysis uses one vintage throughout, apart from the universities from OpenStreetMap.
  The 2026 shortlist combines the competitors of 2026 with the footfall layers of 2019: stations
  opened since (the rest of the Big Circle Line, the MCD lines) are missing, and shops and services
  have surely changed.
- The demand behind the model is that of 2019. Since then the pandemic, remote work, the war and
  sanctions, the exit of foreign chains and the fall of foreign tourism changed where people work,
  shop and spend. The competitors of 2026 reflect the new market, the footfall generators do not.
- The check against 2026 compares two different sources. Their totals around the grid agree, but
  OpenStreetMap misses venues in markets and malls and tags some coffee counters as fast food, so a
  single cell can change for reasons that have nothing to do with the market.
- Competitors are counted, not weighed: a ten-seat coffee counter counts as much as a 200-seat
  restaurant, and price level and concept are ignored.
- There is no data on rents, pedestrian counts, office floor space or incomes; the distance to Red
  Square stands in for tourists and offices.

**Next steps.** Visit the shortlisted places at peak hours, check vacant premises and asking rents,
add office and footfall data (business centres, mobile-operator counts), refresh the 2019 layers,
and rebuild the shortlist every year or two.

## 6. Conclusion

The project looked for places in central Moscow where a new café would share the local footfall
with fewer competitors than usual. The Moscow open data of 2019 on catering, transport, retail and
services were combined on a grid of 364 cells, and a count model learned how many cafés and
restaurants a place normally has given what surrounds it (67% of the deviance explained under
spatial cross-validation). Comparing that expectation with reality shows a saturated historic core
and, mostly 3-6 km from Red Square, places next to metro stations with markedly fewer cafés than
expected.

Seven years later the places the model found under-served in 2019 had 69% more cafés and
restaurants, the saturated ones 11% fewer. The direction agrees with the model, but those were years
of pandemic, war and sanctions that moved cafés from hubs to residential streets on their own, so
the check supports the method without proving it. Run with the competitors of 2026, the same method
points to Savyolovskaya, Maryina Roshcha, Begovaya, Ploshchad Ilyicha and Krasnopresnenskaya as the
strongest candidates today.

The analysis narrows the search from the whole centre to about ten places. The final choice needs
what open data cannot give: a walk around at rush hour, the rent and the concept.
