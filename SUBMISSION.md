# GridBatteryReplay

**Contribution type** Builder → Intelligent Contracts

**Description**

GridBatteryReplay records complete archived Great Britain grid-intensity days. Each GenLayer validator independently fetches the NESO source, checks all 48 intervals and agrees on the exact actual-intensity vector. Missing or malformed observations prevent publication.

A consumer binds a battery dispatch query to a recorded profile ID. The contract calculates an optimal action sequence under explicit demand, capacity, rate and efficiency constraints. It returns grid import, state of charge and the modeled difference from a no-battery baseline.

StudioNet verified two real grid days and four dispatch results against a separate forward optimizer. Ten local tests passed. The calculation uses national average intensity and a simplified 80% efficiency model.

**Evidence**

- [GitHub repository](https://github.com/ehsandto/grid-battery-replay)
- [Exact deployed source](https://github.com/ehsandto/grid-battery-replay/blob/d882d563d575f170c7322e3324fecbcd6529079f/contracts/GridBatteryReplay.py)
- [StudioNet deployment](https://explorer-studio.genlayer.com/address/0xFC3FAEd494F4FF9cd216629D04e593fE5DC75C7B)
- [Live proof matrix](https://github.com/ehsandto/grid-battery-replay/blob/main/LIVE_PROOFS.md)
- [Deploy contract](https://explorer-studio.genlayer.com/tx/0xc24b0a4b87dd38d20b5f1879c65a7e596018a6a59fb969da309a967fea000464)
- [Capture 2025-01-14](https://explorer-studio.genlayer.com/tx/0xa32a1a57e5f70f3b5c55cc4ec87aa5e163031da18f0724a5940f7f620c526ae2)
- [Capture 2025-04-06](https://explorer-studio.genlayer.com/tx/0xfe466665061588357306f1cd6b4fceffdcd2345cdde4a6103e55383126784a29)
