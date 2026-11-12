import fs from 'node:fs';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {rpc, receipt, source, read, digest} from './check.mjs';

const code = 'contracts/GridBatteryReplay.py';
const publisher = {name: 'studio-proof-deployer', address: '0x7a413BB4AB62E31d62d4cD9efC8C8a8Dae37FB42'};
const journal = 'PROOFS.json';
const commit = process.argv[2];
const verifyOnly = process.argv.includes('--verify-only');
assert(/^[a-f0-9]{40}$/.test(commit ?? ''));
const proof = fs.existsSync(journal)
  ? JSON.parse(fs.readFileSync(journal, 'utf8'))
  : {network: 'StudioNet', source_commit: commit, transactions: []};
assert.equal(proof.source_commit, commit);
const save = () => fs.writeFileSync(journal, JSON.stringify(proof, null, 2) + '\n');

function send(args, signer, entry) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['scripts/run-cli.cjs', ...args], {
      windowsHide: true,
      env: {...process.env, GBR_TEST_ACCOUNT: signer.name},
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let pending = '';
    child.stderr.resume();
    child.stdout.on('data', chunk => {
      const lines = (pending + chunk.toString()).split(/\r?\n/);
      pending = lines.pop();
      for (const line of lines) {
        const matched = /^BROADCAST_HASH (0x[0-9a-f]{64})$/i.exec(line);
        if (matched) {
          entry.hash = matched[1];
          save();
          console.log(entry.step, entry.hash);
        }
      }
    });
    child.on('error', reject);
    child.on('close', resolve);
  });
}

async function transaction(step, args, signer) {
  let entry = proof.transactions.find(item => item.step === step);
  if (!entry) {
    assert(!verifyOnly, 'Verification requires an original broadcast journal');
    const nonce = await rpc('eth_getTransactionCount', [signer.address, 'latest']);
    assert.equal(await rpc('eth_getTransactionCount', [signer.address, 'pending']), nonce);
    entry = {step, args, signer: signer.address, nonce};
    proof.transactions.push(entry);
    save();
    await send(args, signer, entry);
  }
  assert.deepEqual(entry.args, args);
  assert.equal(entry.signer, signer.address);
  assert(entry.hash, 'Broadcast status unknown. Inspect account history before any retry.');
  entry.receipt = await receipt(entry.hash);
  save();
  assert(entry.receipt.committed, 'Transaction did not commit');
  const native = await rpc('eth_getTransactionByHash', [entry.hash]);
  assert.equal(native.from_address.toLowerCase(), signer.address.toLowerCase());
  assert.equal(BigInt(native.nonce), BigInt(entry.nonce));
  assert.equal(BigInt(native.value), 0n);
  console.log(step, entry.receipt.status, entry.receipt.execution);
  return entry.receipt.address;
}




const reference = JSON.parse(fs.readFileSync('REFERENCE.json', 'utf8'));
const days = Object.keys(reference);
assert.deepEqual(days, ['2025-01-14', '2025-04-06']);

function earlier(left, right) {
  if (!right) return true;
  for (const [i, item] of left.entries()) {
    if (item !== right[i]) return item < right[i];
  }
  return false;
}

function forward(intensities, loads, capacity, rate) {
  let active = new Map([[0, [0, 0]]]);
  for (const [slot, intensity] of intensities.entries()) {
    const next = new Map();
    for (const [state, partial] of active) {
      for (let end = 0; end <= capacity; end++) {
        const action = end - state;
        if (Math.abs(action) > rate || action < -loads[slot]) continue;
        const energy = 4 * loads[slot] + action * (action > 0 ? 5 : 4);
        const score = [partial[0] + energy * intensity, partial[1] + Math.abs(action),
          ...partial.slice(2), action];
        if (earlier(score, next.get(end))) next.set(end, score);
      }
    }
    active = next;
  }
  const [emissions, movement, ...actions] = active.get(0);
  const states = [0];
  const imports = actions.map((action, i) => {
    states.push(states.at(-1) + action);
    return 4 * loads[i] + action * (action > 0 ? 5 : 4);
  });
  const baseline = intensities.reduce((sum, value, i) => sum + value * loads[i] * 4, 0);
  return {actions, charge_quanta: states, grid_kwh: imports, baseline_gco2: baseline,
    modeled_gco2: emissions, avoided_gco2: baseline - emissions, moved_quanta: movement};
}

assert.equal(await rpc('eth_chainId', []), '0xf22f');
proof.address = await transaction('deploy', ['deploy', '--contract', code], publisher);
proof.source = await source(proof.address);
proof.days ??= {};
save();

for (const day of days) {
  assert.equal(await transaction('capture-' + day,
    ['write', proof.address, 'capture', '--args', day], publisher), proof.address);
  const profile = await read(proof.address, 'get_profile', [day]);
  const evidence = reference[day];
  assert.deepEqual(profile, {...evidence, id: digest(evidence)});
  const result = {profile, scenarios: {}};
  proof.days[day] = result;
  save();
  const demand = Array(48).fill(1);
  for (const [scenario, capacity, rate] of [['battery', 2, 1], ['no_battery', 0, 0]]) {
    const plan = await read(proof.address, 'plan', [day, profile.id, demand, capacity, rate]);
    result.scenarios[scenario] = {demand, capacity, rate, plan};
    save();
    assert.deepEqual(plan, {day, profile_id: profile.id, ...forward(evidence.actual, demand, capacity, rate)});
    if (scenario === 'battery') assert(plan.avoided_gco2 > 0);
    else assert.equal(plan.avoided_gco2, 0);
    console.log(day, scenario, plan.baseline_gco2, '→', plan.modeled_gco2);
  }
}
const history = await rpc('sim_getTransactionsForAddress', [proof.address]);
assert.deepEqual(history.map(t => t.hash).sort(), proof.transactions.map(t => t.hash).sort());
proof.verified = true;
save();
console.log('Verified two archived profiles and four replay results against independent references.');
