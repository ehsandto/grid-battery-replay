import fs from 'node:fs';
import assert from 'node:assert/strict';

const proof = JSON.parse(fs.readFileSync('PROOFS.json', 'utf8'));
const {address, source_commit: commit, source, transactions, days} = proof;
assert(proof.verified && source.source_match);
assert.equal(transactions.length, 3);
assert(transactions.every(t => t.receipt.committed && t.receipt.status === 'FINALIZED'));
assert.equal(Object.keys(days).length, 2);

const repo = 'https://github.com/ehsandto/grid-battery-replay';
const explorer = 'https://explorer-studio.genlayer.com';
const deployed = '[StudioNet deployment](' + explorer + '/address/' + address + ')';
const code = '[Exact deployed source](' + repo + '/blob/' + commit + '/contracts/GridBatteryReplay.py)';
const tx = t => '[' + (t.step === 'deploy' ? 'Deploy contract' : 'Capture ' + t.step.slice(8)) + '](' + explorer + '/tx/' + t.hash + ')';
const rows = Object.entries(days).flatMap(([day, record]) => {
  assert.equal(record.profile.actual.length, 48);
  return Object.entries(record.scenarios).map(([scenario, {plan}]) =>
    '| ' + day + ' | ' + (scenario === 'battery' ? 'Battery' : 'No battery') + ' | ' + plan.baseline_gco2 +
    ' | ' + plan.modeled_gco2 + ' | ' + plan.avoided_gco2 + ' |');
});
assert.equal(rows.length, 4);

fs.writeFileSync('LIVE_PROOFS.md', [
  '# StudioNet evidence', '',
  '- ' + deployed, '- ' + code,
  '- [Receipts and replay traces](PROOFS.json)',
  '- [Independently captured reference vectors](REFERENCE.json)',
  '- Deployed source SHA-256 ' + source.sha256,
  '', '| Finalized transaction | Execution | Agree votes |', '|---|---|---:|',
  ...transactions.map(t => '| ' + tx(t) + ' | ' + t.receipt.execution + ' | ' + t.receipt.agree_votes + ' |'),
  '', '| UTC day | Scenario | Baseline gCO₂ | Modeled gCO₂ | Modeled difference gCO₂ |', '|---|---|---:|---:|---:|',
  ...rows, '',
  'The replay uses 4 kWh of demand per half hour. The battery case can hold two quanta and move one per half hour, with 5 kWh charged per quantum and 4 kWh discharged. Both replays begin and end empty. A separate forward optimizer checked every returned action, battery state and grid import. Ten local tests include 243 exhaustive cases.',
  '',
  'Grid intensity comes from NESO under CC BY 4.0. These are modeled historical estimates using national average intensity. [NESO data and terms](https://carbonintensity.org.uk/)',
  '',
].join('\n'));

const description = [
  'GridBatteryReplay records complete archived Great Britain grid-intensity days. Each GenLayer validator independently fetches the NESO source, checks all 48 intervals and agrees on the exact actual-intensity vector. Missing or malformed observations prevent publication.',
  'A consumer binds a battery dispatch query to a recorded profile ID. The contract calculates an optimal action sequence under explicit demand, capacity, rate and efficiency constraints. It returns grid import, state of charge and the modeled difference from a no-battery baseline.',
  'StudioNet verified two real grid days and four dispatch results against a separate forward optimizer. Ten local tests passed. The calculation uses national average intensity and a simplified 80% efficiency model.',
].join('\n\n');
assert(description.length <= 1000);
fs.writeFileSync('SUBMISSION.md', [
  '# GridBatteryReplay', '', '**Contribution type** Builder → Intelligent Contracts', '',
  '**Description**', '', description, '',
  '**Evidence**', '', '- [GitHub repository](' + repo + ')', '- ' + code, '- ' + deployed,
  '- [Live proof matrix](' + repo + '/blob/main/LIVE_PROOFS.md)',
  ...transactions.map(t => '- ' + tx(t)), '',
].join('\n'));
