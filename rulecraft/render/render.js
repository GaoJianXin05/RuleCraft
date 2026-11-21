// Render scene specs (JSON) to PNG with prismarine-viewer in a headless Edge window.
// Usage: node render.js <scenes.json> <outDir> [--only id1,id2] [--wait ms]
const fs = require('fs')
const path = require('path')
const http = require('http')
const express = require('express')
const { Vec3 } = require('vec3')
const { setupRoutes } = require('prismarine-viewer/lib/common')
const { chromium } = require('playwright-core')

const VERSION = '1.20.1'
const mcData = require('minecraft-data')(VERSION)
const Chunk = require('prismarine-chunk')(VERSION)
const World = require('prismarine-world')(VERSION)
const Block = require('prismarine-block')(VERSION)

const GROUND_Y = 3 // top ground layer; scene blocks start at y = 4

function blockFromSpec (spec, biomeId) {
  if (!mcData.blocksByName[spec.name]) throw new Error(`unknown block ${spec.name}`)
  return Block.fromProperties(spec.name, spec.props || {}, biomeId)
}

function buildWorld (scene) {
  const biome = mcData.biomesByName[scene.biome || 'plains'].id
  const surface = mcData.blocksByName[scene.ground === 'sand' ? 'sand' : 'grass_block'].defaultState
  const under = mcData.blocksByName[scene.ground === 'sand' ? 'sandstone' : 'dirt'].defaultState
  const generator = (cx, cz) => {
    const chunk = new Chunk({ minY: -64, worldHeight: 384 })
    for (let x = 0; x < 16; x++) {
      for (let z = 0; z < 16; z++) {
        for (let y = 0; y < GROUND_Y; y++) chunk.setBlockStateId(new Vec3(x, y, z), under)
        chunk.setBlockStateId(new Vec3(x, GROUND_Y, z), surface)
        for (let y = 0; y < 16; y += 4) chunk.setBiome(new Vec3(x, y, z), biome)
      }
    }
    return chunk
  }
  const world = new World(generator)
  return world
}

async function placeBlocks (world, scene) {
  const biome = mcData.biomesByName[scene.biome || 'plains'].id
  for (const b of scene.blocks) {
    await world.setBlock(new Vec3(b.x, b.y, b.z), blockFromSpec(b, biome))
  }
}

function cameraPose (cam) {
  const [px, py, pz] = cam.pos
  const [tx, ty, tz] = cam.target
  const dx = tx - px; const dy = ty - (py + 1.62); const dz = tz - pz
  const yaw = Math.atan2(-dx, -dz)
  const pitch = Math.atan2(dy, Math.hypot(dx, dz))
  return { pos: { x: px, y: py, z: pz }, yaw, pitch }
}

async function main () {
  const [scenesPath, outDir, ...rest] = process.argv.slice(2)
  const only = rest.includes('--only') ? rest[rest.indexOf('--only') + 1].split(',') : null
  const waitMs = rest.includes('--wait') ? parseInt(rest[rest.indexOf('--wait') + 1], 10) : 4500
  let scenes = JSON.parse(fs.readFileSync(scenesPath, 'utf8'))
  if (only) scenes = scenes.filter(s => only.includes(s.id))
  fs.mkdirSync(outDir, { recursive: true })

  const app = express()
  setupRoutes(app, '')
  const server = http.createServer(app)
  const io = require('socket.io')(server)
  let current = null
  io.on('connection', async (socket) => {
    const { world, scene } = current
    socket.emit('version', VERSION)
    const r = scene.viewDistance || 1
    for (let x = -r; x <= r; x++) {
      for (let z = -r; z <= r; z++) {
        const chunk = (await world.getColumn(x, z)).toJson()
        socket.emit('loadChunk', { x: x * 16, z: z * 16, chunk })
      }
    }
    setTimeout(() => socket.emit('position', cameraPose(scene.camera)), 300)
  })
  await new Promise(resolve => server.listen(0, resolve))
  const port = server.address().port

  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
  for (const scene of scenes) {
    const out = path.join(outDir, `${scene.id}.png`)
    if (fs.existsSync(out) && !rest.includes('--force')) continue
    const world = buildWorld(scene)
    await placeBlocks(world, scene)
    current = { world, scene }
    const page = await browser.newPage({ viewport: { width: scene.width || 768, height: scene.height || 480 } })
    await page.goto(`http://localhost:${port}/`)
    await page.waitForTimeout(waitMs)
    await page.screenshot({ path: out })
    await page.close()
    console.log('rendered', scene.id)
  }
  await browser.close()
  server.close()
  process.exit(0)
}

main().catch(err => { console.error(err); process.exit(1) })
