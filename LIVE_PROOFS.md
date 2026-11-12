# StudioNet evidence

- [StudioNet deployment](https://explorer-studio.genlayer.com/address/0xFC3FAEd494F4FF9cd216629D04e593fE5DC75C7B)
- [Exact deployed source](https://github.com/ehsandto/grid-battery-replay/blob/d882d563d575f170c7322e3324fecbcd6529079f/contracts/GridBatteryReplay.py)
- [Receipts and replay traces](PROOFS.json)
- [Independently captured reference vectors](REFERENCE.json)
- Deployed source SHA-256 b22ee032ef1181b4cb61f7cdae2ed0e3551432efdb4b06bcdcb94c3861b70c8c

| Finalized transaction | Execution | Agree votes |
|---|---|---:|
| [Deploy contract](https://explorer-studio.genlayer.com/tx/0xc24b0a4b87dd38d20b5f1879c65a7e596018a6a59fb969da309a967fea000464) | SUCCESS | 3 |
| [Capture 2025-01-14](https://explorer-studio.genlayer.com/tx/0xa32a1a57e5f70f3b5c55cc4ec87aa5e163031da18f0724a5940f7f620c526ae2) | SUCCESS | 3 |
| [Capture 2025-04-06](https://explorer-studio.genlayer.com/tx/0xfe466665061588357306f1cd6b4fceffdcd2345cdde4a6103e55383126784a29) | SUCCESS | 3 |

| UTC day | Scenario | Baseline gCO₂ | Modeled gCO₂ | Modeled difference gCO₂ |
|---|---|---:|---:|---:|
| 2025-01-14 | Battery | 36236 | 35430 | 806 |
| 2025-01-14 | No battery | 36236 | 36236 | 0 |
| 2025-04-06 | Battery | 19544 | 18741 | 803 |
| 2025-04-06 | No battery | 19544 | 19544 | 0 |

The replay uses 4 kWh of demand per half hour. The battery case can hold two quanta and move one per half hour, with 5 kWh charged per quantum and 4 kWh discharged. Both replays begin and end empty. A separate forward optimizer checked every returned action, battery state and grid import. Ten local tests include 243 exhaustive cases.

Grid intensity comes from NESO under CC BY 4.0. These are modeled historical estimates using national average intensity. [NESO data and terms](https://carbonintensity.org.uk/)
