# GridBatteryReplay

Replay battery dispatch against archived Great Britain grid carbon intensity. Each GenLayer validator independently retrieves a complete day from the National Energy System Operator, validates every half-hour interval, and agrees on the exact vector of `actual` values. The contract stores a content-addressed profile. [NESO API](https://api.carbonintensity.org.uk/) · [GenLayer nondeterminism](https://docs.genlayer.com/developers/intelligent-contracts/features/non-determinism)

`capture(day)` accepts a completed UTC day in YYYY-MM-DD format. It requires 48 contiguous half-hour observations and ignores the API's optional interval ending at midnight before the requested window. Missing, duplicated, out-of-window or non-integer actual observations prevent publication. The first agreed capture is immutable. `get_profile(day)` returns the accepted values, source URL and profile ID.

`plan(day, profile_id, demand, capacity, rate)` computes a dispatch schedule. Demand has 48 entries, each in whole quanta of 4 kWh. Capacity is 0 to 12 quanta. Rate is 0 to 4 quanta per half hour in either direction. Charging consumes 5 kWh per stored quantum and discharging supplies 4 kWh. The battery begins and ends empty, and discharge never exceeds demand. The optimizer minimizes modeled grams of CO₂, then battery throughput, then the lexicographic action sequence. The result contains every action, battery state and grid import, plus the no-battery baseline and modeled difference.

The `actual` series is NESO's estimate from metered generation. The output is a historical simulation using national average intensity and a fixed 80% round-trip efficiency. Physical equipment limits and marginal emissions require separate modeling. The two vectors in `REFERENCE.json` are normalized from NESO's Carbon Intensity API under CC BY 4.0. [NESO methodology and terms](https://carbonintensity.org.uk/) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

```sh
python -m pip install -r requirements-dev.txt
genvm-lint check contracts/GridBatteryReplay.py
python -m pytest tests -q
```

[StudioNet contract](https://explorer-studio.genlayer.com/address/0xFC3FAEd494F4FF9cd216629D04e593fE5DC75C7B) · [Live proofs](LIVE_PROOFS.md) · [Submission text](SUBMISSION.md)
