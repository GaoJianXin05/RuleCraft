// Engine check: build every scene on a vanilla 1.20.1 server, perform the action, and test the resulting blocks.
// Usage (from rulecraft/engine): node verify.js   -> writes ../results/engine_check.json
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')
const mineflayer = require('../render/node_modules/mineflayer')
const { Vec3 } = require('../render/node_modules/vec3')

const SERVER_DIR = path.join(__dirname, 'server')
const SPLIT = process.argv[2] || null
const ONLY = process.argv[3] ? process.argv[3].split(',') : null   // optional comma-separated rule ids: re-check and merge
// PLAN_FILE / OUT_FILE (optional): check a hand-made subset of the plan without touching the stored results
const PLAN = JSON.parse(fs.readFileSync(process.env.PLAN_FILE || path.join(__dirname, '..', 'data', 'engine_plan.json'), 'utf8'))
  .filter(p => (!SPLIT || p.split === SPLIT) && (!ONLY || ONLY.includes(p.rule)))
const OUT = process.env.OUT_FILE || path.join(__dirname, '..', 'results', SPLIT ? `engine_check_${SPLIT}.json` : 'engine_check.json')
// progress is saved after every scene, so an interrupted run continues where it stopped (not when re-checking some rules)
const PARTIAL = OUT.replace(/\.json$/, '_partial.json')
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

let lines = []
const server = spawn('java', ['-Xmx2G', '-jar', 'server.jar', 'nogui'], { cwd: SERVER_DIR })
server.stdout.on('data', d => { for (const l of d.toString().split(/\r?\n/)) if (l.trim()) lines.push(l) })
server.stderr.on('data', d => process.stderr.write(d))
const cmd = c => server.stdin.write(c.replace(/^\//, '') + '\n')

async function waitFor (re, timeoutMs = 180000, from = 0) {
  const t0 = Date.now()
  while (Date.now() - t0 < timeoutMs) {
    for (let i = from; i < lines.length; i++) if (re.test(lines[i])) return i
    await sleep(100)
  }
  throw new Error('timeout waiting for ' + re)
}

async function test (tag, check) {
  const mark = `CHK ${tag}`
  const from = lines.length
  const pos = check.pos.join(' ')
  cmd(`say ${mark}`)
  if (check.entity) {
    const [x, y, z] = check.pos
    cmd(`execute ${check.absent ? 'unless' : 'if'} entity @e[type=${check.entity},x=${x},y=${y},z=${z},distance=..${check.r}]`)
  } else {
    cmd(`execute ${check.negate ? 'unless' : 'if'} block ${pos} ${check.block}`)
  }
  const i = await waitFor(new RegExp(mark.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'), 20000, from)
  const j = await waitFor(/Test (passed|failed)/, 20000, i)
  return /Test passed/.test(lines[j])
}

async function main () {
  await waitFor(/Done \(/)
  console.log('server ready')
  const bot = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: 'verifier', version: '1.20.1', auth: 'offline' })
  await new Promise((resolve, reject) => { bot.once('spawn', resolve); bot.once('error', reject) })
  for (const c of ['gamerule doDaylightCycle false', 'time set noon', 'weather clear 1000000', 'gamerule doWeatherCycle false',
    'gamerule doMobSpawning false', 'gamerule randomTickSpeed 3', 'gamemode survival verifier', 'difficulty peaceful']) cmd(c)
  await sleep(1000)

  const results = !ONLY && fs.existsSync(PARTIAL) ? JSON.parse(fs.readFileSync(PARTIAL, 'utf8')) : []
  const done = new Set(results.map(r => r.id))
  if (done.size) console.log(`resuming: ${done.size}/${PLAN.length} scenes already checked`)
  for (const p of PLAN) {
    if (done.has(p.id)) continue
    const [ox, oz] = p.site
    const [bx, bz] = p.bot || [2, 2]
    cmd(`tp verifier ${ox + bx + 0.5} -60 ${oz + bz + 0.5}`)
    await sleep(1500)
    for (const c of (p.action.pre || [])) cmd(c)
    cmd(`fill ${ox - 10} -60 ${oz - 10} ${ox + 10} -50 ${oz + 10} minecraft:air`)
    cmd(`fill ${ox - 10} -62 ${oz - 10} ${ox + 10} -62 ${oz + 10} minecraft:dirt`)
    cmd(`fill ${ox - 10} -61 ${oz - 10} ${ox + 10} -61 ${oz + 10} minecraft:${p.ground === 'sand' ? 'sand' : 'grass_block'}`)
    cmd(`fillbiome ${ox - 10} -64 ${oz - 10} ${ox + 10} -40 ${oz + 10} minecraft:${p.biome}`)
    // let block events left by a previous build (e.g. a retracting piston) fire on air, not on the new scene
    await sleep(1000)
    for (const c of p.build) cmd(c)
    await sleep(800)
    const a = p.action
    if (a.type === 'cmd') {
      for (const c of a.cmds) cmd(c)
      for (const c of (a.after || [])) cmd(c)
    } else if (a.type === 'ticks_only') {
      await sleep(a.seconds * 1000)
    } else if (a.type === 'ticks') {
      cmd(`gamerule randomTickSpeed ${a.speed}`)
      await sleep(a.seconds * 1000)
      cmd('gamerule randomTickSpeed 3')
    } else if (a.type === 'dig') {
      const target = bot.blockAt(new Vec3(...a.pos))
      try { await bot.dig(target, true) } catch (e) { console.log('dig failed', p.id, e.message) }
    }
    await sleep(p.wait_ticks * 50 + 300)
    const checks = []
    for (let k = 0; k < p.checks.length; k++) {
      const c = p.checks[k]
      checks.push({ ...c, pass: await test(`${p.id} ${k}`, c) })
    }
    for (const c of (a.post || [])) cmd(c)
    const pass = checks.every(c => c.pass)
    results.push({ id: p.id, rule: p.rule, pass, checks })
    if (!ONLY) fs.writeFileSync(PARTIAL, JSON.stringify(results, null, 1))
    console.log(pass ? 'PASS' : 'FAIL', p.id, checks.filter(c => !c.pass).map(c => `${c.block}@${c.pos}`).join(' '))
  }
  // when re-checking some rules, keep the stored results of the others
  const kept = ONLY && fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf8')).filter(r => !ONLY.includes(r.rule)) : []
  fs.writeFileSync(OUT, JSON.stringify(kept.concat(results), null, 1))
  if (fs.existsSync(PARTIAL)) fs.unlinkSync(PARTIAL)
  const nPass = results.filter(r => r.pass).length
  console.log(`engine check: ${nPass}/${results.length} scenes match the vanilla label`)
  bot.quit()
  cmd('stop')
  await sleep(5000)
  process.exit(0)
}

main().catch(e => { console.error(e); cmd('stop'); setTimeout(() => process.exit(1), 5000) })
