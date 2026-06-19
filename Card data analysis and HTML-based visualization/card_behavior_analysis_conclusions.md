# Beijing Metro AFC Data · Individual Card Behavior Analysis Conclusions

> Data source: February 21–27, 2018 Beijing Metro AFC card swiping data (7 days total)

---

## 1. Data Scale

| Metric | Value |
|--------|-------|
| Raw trip records | 25.78 million |
| Total unique cards (passengers) | 6.48 million |
| Active passengers (>=3 trips) | 3.17 million |
| Weekday trips | 15.84 million |
| Weekend trips | 5.32 million |

Weekday trip volume is approximately **3 times** that of weekends, reflecting that the Beijing Metro primarily serves commuting needs.

---

## 2. Commuter Pattern Detection

**Approximately 1.01 million passengers identified as regular commuters, accounting for 32% of active passengers.**

Detection criteria:
- >=4 days of travel in 7 days
- Same OD (entry-exit station pair) accounts for >=35% of the card's total trips
- Weekday morning peak (6–9AM) or evening peak (5–8PM) trips account for >=40%

The entry time distribution shows a **clear bimodal pattern**:
- Morning peak concentrated between **7–8AM**
- Evening peak concentrated between **6–7PM**

Entry volume during these two peak periods significantly surpasses all other time slots, strongly consistent with the high proportion of commuters.

---

## 3. Fare Distribution

- Fare is concentrated in the **3–5 CNY** range, with **4 CNY** being the most frequent (approximately 7.7 million trips)
- This indicates the majority of passengers take **short-to-medium distance trips**, with daily commuting within the core urban area being the primary use case
- Very few trips reach 25 CNY, representing a small number of long-distance suburban journeys

---

## 4. Ride Duration Distribution

- The most concentrated range is **20–40 minutes**, totaling approximately 8.6 million trips
- The proportion of long-distance trips exceeding 60 minutes declines rapidly as duration increases
- However, a notable number of 60–90 minute suburban commuters still exist

---

## 5. Passenger Clustering (K-Means, k=5)

50,000 cards randomly sampled from 3.17 million active passengers, with 9-dimensional features extracted for clustering:

> Feature dimensions: avg trips per day, entry time mean/std, weekday ratio, morning peak ratio, evening peak ratio, avg ride duration, avg fare, OD concentration

| Type | Characteristic Description |
|------|---------------------------|
| 🕐 Fixed Commuters | High weekday frequency, highly regular entry times, fixed routes, high peak-hour hit rate |
| 🌆 Light Commuters | Primarily weekday travel, relatively fixed times but more diverse routes, moderate fares |
| 🧭 Flexible Travelers | Scattered travel times, not concentrated during peak hours, diverse routes, non-commuter traits |
| 🎉 Weekend Leisure | High proportion of weekend/non-workday travel, afternoon-focused, lower fares |
| 🚄 Long-distance Heavy Users | Long travel distance per trip, high fare, but low frequency; may be suburban commuters or migrant workers |

---

## 6. Key Conclusions

1. **Beijing Metro ridership is highly dependent on commuting demand**: The 3:1 weekday-to-weekend trip ratio and the clear bimodal time distribution both point to commuting as the core use case of the metro system.

2. **About one-third of active passengers exhibit strong regularity**: 1.01 million regular commuters have fixed routes and consistent schedules, forming the most stable and predictable user group of the metro system.

3. **A large number of cards represent occasional travel**: Nearly half of the 6.48 million total cards (3.31 million) took fewer than 3 trips in 7 days, indicating a large population of incidental, non-daily passengers.

4. **Passenger behavior is highly stratified**: K-Means clustering clearly divides passengers into five distinct types, with significant differences in travel time, frequency, and distance, reflecting the diversity of populations served by the Beijing Metro.

5. **Short-to-medium distance trips dominate**: Fares concentrated in the 3–5 CNY range and durations concentrated in the 20–40 minute range confirm that the metro primarily serves daily short-to-medium distance travel within the urban core.
