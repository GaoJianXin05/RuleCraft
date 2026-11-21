using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Microsoft.Xna.Framework;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Menus;
using StardewValley.Objects;
using StardewValley.TerrainFeatures;
using StardewValley.Tools;
using SObject = StardewValley.Object;

namespace SceneLab
{
    /// <summary>Reads jobs/job.json, and for every scene: clears a patch of the farm, sets the date and weather, builds the
    /// scene, takes a map screenshot, performs the steps (tool use, harvest, days passing) and writes the game state of
    /// every scene tile before and after. All game rules are the game's own: days pass through the game's sleep command.</summary>
    public class ModEntry : Mod
    {
        private IEnumerator routine;
        private Func<bool> waitUntil;
        private int waitTicks;
        private bool dayStarted;
        private bool? rainTomorrow;
        private readonly Stack<IEnumerator> stack = new Stack<IEnumerator>();
        private bool newGameRequested;
        private JObject job;
        private string outDir;
        private StreamWriter log;

        public override void Entry(IModHelper helper)
        {
            helper.Events.GameLoop.UpdateTicked += OnTick;
            NoFarmSurprises("RuleCraft.SceneLab");
            helper.Events.GameLoop.DayStarted += (s, e) => dayStarted = true;
            helper.Events.GameLoop.DayEnding += (s, e) => { if (rainTomorrow.HasValue) SetRainTomorrow(rainTomorrow.Value); };
            helper.Events.Display.Rendered += OnRendered;
            string jobPath = Path.Combine(helper.DirectoryPath, "jobs", "job.json");
            if (!File.Exists(jobPath)) { Monitor.Log("no job file", LogLevel.Warn); return; }
            job = JObject.Parse(File.ReadAllText(jobPath));
            outDir = (string)job["out"];
            Directory.CreateDirectory(outDir);
            log = new StreamWriter(Path.Combine(outDir, "_log.txt"), append: false) { AutoFlush = true };
            routine = Main();
        }

        /// <summary>No night events (fairy, meteorite, witch, ...) and no crows: overnight, only the rules under test act.</summary>
        private static void NoFarmSurprises(string id)
        {
            var h = new HarmonyLib.Harmony(id);
            h.Patch(AccessTools(typeof(Utility), "pickFarmEvent"), postfix: new HarmonyLib.HarmonyMethod(typeof(ModEntry), nameof(NullEvent)));
            h.Patch(AccessTools(typeof(Utility), "pickPersonalFarmEvent"), postfix: new HarmonyLib.HarmonyMethod(typeof(ModEntry), nameof(NullEvent)));
            h.Patch(AccessTools(typeof(Farm), "addCrows"), prefix: new HarmonyLib.HarmonyMethod(typeof(ModEntry), nameof(Skip)));
            h.Patch(AccessTools(typeof(GameLocation), "checkForEvents"), prefix: new HarmonyLib.HarmonyMethod(typeof(ModEntry), nameof(Skip)));   // no cutscenes
        }
        private static MethodInfo AccessTools(Type t, string name) => t.GetMethod(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance);
        private static void NullEvent(ref StardewValley.Events.FarmEvent __result) { __result = null; }
        private static bool Skip() => false;

        private static Dictionary<string, int> Inventory()
        {
            var d = new Dictionary<string, int>();
            foreach (var it in Game1.player.Items) if (it != null) { d.TryGetValue(it.QualifiedItemId, out int c); d[it.QualifiedItemId] = c + it.Stack; }
            return d;
        }

        private void Log(string s) { Monitor.Log(s, LogLevel.Info); log?.WriteLine($"{DateTime.Now:HH:mm:ss} {s}"); }

        private void OnTick(object sender, UpdateTickedEventArgs e)
        {
            if (routine == null) return;
            if (stack.Count == 0) stack.Push(routine);
            if (waitTicks > 0) { waitTicks--; return; }
            if (waitUntil != null)
            {
                if (!waitUntil())
                {
                    if (++waitedTicks % 600 == 0)
                        Log($"still waiting ({waitedTicks} ticks): menu={Game1.activeClickableMenu?.GetType().Name} loc={Game1.currentLocation?.Name} " +
                            $"free={Context.IsPlayerFree} newDay={Game1.newDay} fade={Game1.globalFade} time={Game1.timeOfDay} {DateString()}");
                    return;
                }
                waitUntil = null; waitedTicks = 0;
            }
            try
            {
                var top = stack.Peek();
                if (!top.MoveNext())
                {
                    stack.Pop();
                    if (stack.Count == 0) routine = null;
                    return;
                }
                switch (top.Current)
                {
                    case int n: waitTicks = n; break;
                    case Func<bool> f: waitUntil = f; break;
                    case IEnumerator sub: stack.Push(sub); break;
                }
            }
            catch (Exception ex)
            {
                Log("FATAL " + ex);
                routine = null;
                File.WriteAllText(Path.Combine(outDir, "_done.txt"), "error");
            }
        }

        // ------------------------------------------------------------------------------------------- main routine
        private IEnumerator Main()
        {
            // 1. a fresh standard farm, no intro, nothing saved
            yield return (Func<bool>)(() => Game1.activeClickableMenu is TitleMenu);
            yield return 60;
            KeepRunningInBackground();
            Game1.resetPlayer();
            Game1.player.Name = "Lab";
            Game1.player.farmName.Value = "Lab";
            Game1.player.favoriteThing.Value = "Science";
            Game1.whichFarm = 0;
            Game1.player.isCustomized.Value = true;
            ((TitleMenu)Game1.activeClickableMenu).createdNewCharacter(true);
            yield return (Func<bool>)(() => Context.IsWorldReady && Game1.activeClickableMenu == null && !Game1.eventUp && Game1.currentLocation != null);
            yield return 30;
            Game1.saveOnNewDay = false;
            Game1.stats.DaysPlayed = 200;          // past the first-year scripted weather (rain on day 3) and tutorials
            KeepRunningInBackground();
            Log($"world ready: {Game1.currentLocation.Name} {Game1.season} {Game1.dayOfMonth} y{Game1.year}");

            foreach (JObject sc in job["items"])
            {
                string id = (string)sc["id"];
                if (File.Exists(Path.Combine(outDir, id + ".json"))) continue;
                JObject result = new JObject { ["id"] = id };
                IEnumerator inner = RunScene(sc, result);
                while (true)
                {
                    bool more;
                    try { more = inner.MoveNext(); }
                    catch (Exception ex) { Log($"{id} ERROR {ex.Message}"); result["error"] = ex.ToString(); break; }
                    if (!more) break;
                    yield return inner.Current;
                }
                File.WriteAllText(Path.Combine(outDir, id + ".json"), result.ToString(Formatting.Indented));
                Log($"{id} done");
            }
            File.WriteAllText(Path.Combine(outDir, "_done.txt"), "ok");
            Log("all done");
            if ((bool?)job["exit"] ?? true)
            {
                yield return 30;
                Environment.Exit(0);
            }
        }

        // ------------------------------------------------------------------------------------------- one scene
        private IEnumerator RunScene(JObject sc, JObject result)
        {
            Farm farm = Game1.getFarm();
            int ox = (int)sc["origin"][0], oy = (int)sc["origin"][1];
            sceneOrigin = new Point(ox, oy);
            Rectangle clear = new Rectangle(ox - 13, oy - 8, 27, 17);

            // date, time and weather of the first day
            if (Game1.currentLocation != farm)
            {
                Game1.warpFarmer("Farm", 64, 15, 2);
                yield return (Func<bool>)(() => Game1.currentLocation == farm && !Game1.isWarping && Game1.activeClickableMenu == null);
                yield return 10;
            }
            SetDate((string)sc["season"] ?? "spring", (int?)sc["day"] ?? 5, (int?)sc["year"] ?? 2);
            SetRainToday((bool?)sc["rain_today"] ?? false);
            Game1.timeOfDay = (int?)sc["time"] ?? 900;
            ClearArea(farm, clear);
            yield return 5;

            // scene
            foreach (JObject t in sc["tiles"]) Place(farm, ox, oy, t);
            yield return 20;
            result["date_before"] = DateString();
            result["before"] = Dump(farm, ox, oy, sc);
            yield return Shot(farm, (string)sc["id"] + "_before", result, "shot_before");

            var held = Inventory();                                       // items the farmer picks up count as dropped
            // steps
            foreach (JObject st in sc["steps"] ?? new JArray())
            {
                string op = (string)st["op"];
                if (op == "tool")
                {
                    int hits = (int?)st["hits"] ?? 1;
                    Vector2 tile = new Vector2(ox + (int)st["d"][0], oy + (int)st["d"][1]);
                    for (int k = 0; k < hits; k++)
                    {
                        UseTool(farm, (string)st["tool"], tile, (int?)st["level"] ?? 0);
                        yield return 15;
                    }
                    yield return (int?)st["settle"] ?? 180;          // let falling trees and debris finish
                }
                else if (op == "harvest")
                {
                    Vector2 tile = new Vector2(ox + (int)st["d"][0], oy + (int)st["d"][1]);
                    Game1.player.Position = new Vector2(tile.X * 64, (tile.Y + 1) * 64);
                    if (farm.terrainFeatures.TryGetValue(tile, out var tf) && tf is HoeDirt hd && hd.crop != null)
                    {
                        bool ok = hd.crop.harvest((int)tile.X, (int)tile.Y, hd);       // the hand harvest, without the farmer's animation
                        if (ok && !hd.crop.RegrowsAfterHarvest()) hd.destroyCrop(false);
                        result["harvest_" + st["d"][0] + "_" + st["d"][1]] = ok;
                    }
                    yield return 60;
                }
                else if (op == "water")
                {
                    Vector2 tile = new Vector2(ox + (int)st["d"][0], oy + (int)st["d"][1]);
                    if (farm.terrainFeatures.TryGetValue(tile, out var tf) && tf is HoeDirt hd) hd.state.Value = HoeDirt.watered;
                }
                else if (op == "days")
                {
                    int n = (int)st["n"];
                    JArray rain = st["rain"] as JArray;
                    JArray water = st["water"] as JArray;
                    var weatherLog = new JArray();
                    for (int k = 0; k < n; k++)
                    {
                        if (water != null)
                            foreach (JArray d in water)
                            {
                                Vector2 tile = new Vector2(ox + (int)d[0], oy + (int)d[1]);
                                if (farm.terrainFeatures.TryGetValue(tile, out var tf) && tf is HoeDirt hd) hd.state.Value = HoeDirt.watered;
                            }
                        bool r = rain != null ? (bool)rain[Math.Min(k, rain.Count - 1)] : ((bool?)st["rain_all"] ?? false);
                        rainTomorrow = r;
                        SetRainTomorrow(r);
                        dayStarted = false;
                        Game1.timeOfDay = 2200;
                        DebugCommands.TryHandle(new[] { "sleep" });
                        string before = DateString();
                        for (int g = 0, calm = 0; !dayStarted && g < 6000 && calm < 120; g++)   // a morning dialogue can hold the new day back
                        {
                            bool morning = DateString() != before && !Game1.newDay && Game1.timeOfDay <= 610 && Game1.currentLocation != null
                                           && !(Game1.activeClickableMenu is StardewValley.Menus.SaveGameMenu) && !(Game1.activeClickableMenu is StardewValley.Menus.ShippingMenu);
                            calm = morning ? calm + 1 : 0;
                            if (Game1.activeClickableMenu is StardewValley.Menus.DialogueBox db && DateString() != before)
                            {
                                Log("closing dialogue: " + (db.getCurrentString() ?? "").Replace((char)10, ' '));
                                Game1.exitActiveMenu(); Game1.dialogueUp = false;
                            }
                            yield return 1;
                        }
                        if (!dayStarted) Log("day start taken from the clock: " + DateString());
                        yield return 20;
                        for (int quiet = 0, guard = 0; quiet < 30 && guard < 2000; guard++)   // close any morning dialogue or letter
                        {
                            if (Game1.activeClickableMenu != null || Game1.dialogueUp) { Game1.exitActiveMenu(); Game1.dialogueUp = false; quiet = 0; }
                            else quiet++;
                            yield return 1;
                        }
                        if (Game1.currentLocation != farm)
                        {
                            Game1.warpFarmer("Farm", 64, 15, 2);
                            yield return (Func<bool>)(() => Game1.currentLocation == farm && !Game1.isWarping);
                            yield return 10;
                        }
                        Game1.timeOfDay = (int?)sc["time"] ?? 900;
                        weatherLog.Add($"{DateString()} rain={Game1.isRaining}");
                    }
                    result["days_log"] = weatherLog;
                }
                else if (op == "wait") yield return (int)st["ticks"];
            }
            yield return 30;
            result["date_after"] = DateString();
            result["after"] = Dump(farm, ox, oy, sc);
            var now = Inventory(); var gained = new JArray();
            foreach (var kv in now) { held.TryGetValue(kv.Key, out int c0); if (kv.Value > c0) gained.Add(kv.Key + "x" + (kv.Value - c0)); }
            ((JObject)result["after"])["gained"] = gained;
            yield return Shot(farm, (string)sc["id"] + "_after", result, "shot_after");
        }

        // ------------------------------------------------------------------------------------------- helpers
        /// <summary>The game runs minimized and silent while it builds scenes.</summary>
        private static void KeepRunningInBackground()
        {
            if (Game1.options == null) return;
            Game1.options.singlePlayerBaseZoomLevel = 1.5f;
            Game1.options.desiredBaseZoomLevel = 1.5f;
            Game1.options.baseZoomLevel = 1.5f;
            Game1.game1.refreshWindowSettings();
            Game1.options.pauseWhenOutOfFocus = false;
            Game1.options.musicVolumeLevel = 0f;
            Game1.options.soundVolumeLevel = 0f;
            Game1.options.ambientVolumeLevel = 0f;
            Game1.options.footstepVolumeLevel = 0f;
        }

        private static string DateString() => $"y{Game1.year} {Game1.season} {Game1.dayOfMonth} {Game1.timeOfDay} rain={Game1.isRaining}";

        private void SetDate(string season, int day, int year)
        {
            Game1.year = year;
            Game1.season = Enum.Parse<Season>(season, true);
            Game1.dayOfMonth = day;
            Game1.setGraphicsForSeason();
            foreach (var loc in Game1.locations) loc.seasonUpdate(false);
        }

        private static void SetWeatherField(string field, object value)
        {
            object w = Game1.netWorldState.Value.GetWeatherForLocation("Default");
            var p = w.GetType().GetProperty(field, BindingFlags.Public | BindingFlags.Instance);
            p?.SetValue(w, value);
        }

        private void SetRainToday(bool rain)
        {
            Game1.isRaining = rain;
            Game1.isLightning = false;
            Game1.isSnowing = false;
            Game1.isDebrisWeather = false;
            SetWeatherField("IsRaining", rain);
            SetWeatherField("IsLightning", false);
            SetWeatherField("IsSnowing", false);
            SetWeatherField("IsDebrisWeather", false);
            SetWeatherField("Weather", rain ? Game1.weather_rain : Game1.weather_sunny);
        }

        private void SetRainTomorrow(bool rain)
        {
            string w = rain ? Game1.weather_rain : Game1.weather_sunny;
            Game1.weatherForTomorrow = w;
            SetWeatherField("WeatherForTomorrow", w);
        }

        private static void ClearArea(Farm farm, Rectangle r)
        {
            foreach (var k in farm.terrainFeatures.Keys.Where(v => r.Contains((int)v.X, (int)v.Y)).ToList()) farm.terrainFeatures.Remove(k);
            foreach (var k in farm.objects.Keys.Where(v => r.Contains((int)v.X, (int)v.Y)).ToList()) farm.objects.Remove(k);
            foreach (var f in farm.furniture.Where(f => r.Contains((int)f.TileLocation.X, (int)f.TileLocation.Y)).ToList()) farm.furniture.Remove(f);
            foreach (var c in farm.resourceClumps.Where(c => c.getBoundingBox().Intersects(new Rectangle(r.X * 64, r.Y * 64, r.Width * 64, r.Height * 64))).ToList()) farm.resourceClumps.Remove(c);
            foreach (var b in farm.largeTerrainFeatures.Where(b => r.Contains((int)b.Tile.X, (int)b.Tile.Y)).ToList()) farm.largeTerrainFeatures.Remove(b);
            farm.debris.Clear();
        }

        private void Place(Farm farm, int ox, int oy, JObject t)
        {
            Vector2 tile = new Vector2(ox + (int)t["d"][0], oy + (int)t["d"][1]);
            if ((bool?)t["hoe"] == true)
            {
                var hd = new HoeDirt((bool?)t["water"] == true ? HoeDirt.watered : HoeDirt.dry, farm);
                farm.terrainFeatures[tile] = hd;
                if (t["fertilizer"] != null) hd.plant((string)t["fertilizer"], Game1.player, true);
                if (t["crop"] != null)
                {
                    hd.crop = new Crop((string)t["crop"], (int)tile.X, (int)tile.Y, farm);
                    var phase = t["phase"];
                    if (phase != null && phase.Type == JTokenType.String && (string)phase == "grown") hd.crop.growCompletely();
                    else if (phase != null) { hd.crop.currentPhase.Value = (int)phase; hd.crop.dayOfCurrentPhase.Value = (int?)t["day_of_phase"] ?? 0; }
                    hd.crop.updateDrawMath(tile);
                }
            }
            if (t["flooring"] != null) farm.terrainFeatures[tile] = new Flooring((string)t["flooring"]);
            if (t["tree"] != null)
            {
                var tr = new Tree((string)t["tree"], (int?)t["stage"] ?? 5, false);
                if ((bool?)t["stump"] == true) { tr.stump.Value = true; tr.health.Value = 5f; }
                farm.terrainFeatures[tile] = tr;
            }
            if (t["fruittree"] != null)
            {
                var ft = new FruitTree((string)t["fruittree"], (int?)t["stage"] ?? 4);
                if (((int?)t["stage"] ?? 4) >= 4) ft.daysUntilMature.Value = -1;
                farm.terrainFeatures[tile] = ft;
                for (int k = 0; k < ((int?)t["fruit"] ?? 0); k++) ft.TryAddFruit();
            }
            if (t["obj"] != null)
            {
                Item it = ItemRegistry.Create((string)t["obj"]);
                if (it is SObject o)
                {
                    if (o is Chest ch && t["chest_items"] is JArray items)
                        foreach (JArray x in items) ch.addItem(ItemRegistry.Create((string)x[0], (int)x[1]));
                    if (!o.placementAction(farm, (int)tile.X * 64, (int)tile.Y * 64, Game1.player))
                        farm.objects[tile] = o;
                    if (farm.objects.TryGetValue(tile, out var placed))
                    {
                        if (placed is Chest pc && t["chest_items"] is JArray items2 && pc.Items.Count == 0)
                            foreach (JArray x in items2) pc.addItem(ItemRegistry.Create((string)x[0], (int)x[1]));
                        if (t["on"] != null) placed.IsOn = (bool)t["on"];
                    }
                }
            }
            if (t["drop"] != null)
                for (int k = 0; k < ((int?)t["count"] ?? 1); k++)
                    Game1.createItemDebris(ItemRegistry.Create((string)t["drop"]), new Vector2(tile.X * 64 + 32, tile.Y * 64 + 32), -1, farm);
            if ((bool?)t["spawned"] == true && farm.objects.TryGetValue(tile, out var sp)) sp.IsSpawnedObject = true;
            if (t["furniture"] != null)
            {
                var f = ItemRegistry.Create<Furniture>((string)t["furniture"]);
                f.TileLocation = tile;
                if (t["held"] != null) f.heldObject.Value = ItemRegistry.Create<SObject>((string)t["held"]);
                farm.furniture.Add(f);
            }
        }

        private void UseTool(Farm farm, string name, Vector2 tile, int level)
        {
            Tool tool = name switch
            {
                "axe" => ItemRegistry.Create<Tool>("(T)Axe"),
                "pickaxe" => ItemRegistry.Create<Tool>("(T)Pickaxe"),
                "hoe" => ItemRegistry.Create<Tool>("(T)Hoe"),
                "can" => ItemRegistry.Create<Tool>("(T)WateringCan"),
                "scythe" => ItemRegistry.Create<Tool>("(W)47"),
                _ => throw new ArgumentException(name)
            };
            if (tool is WateringCan wc) wc.WaterLeft = wc.waterCanMax;
            tool.UpgradeLevel = level;
            var who = Game1.player;
            tool.lastUser = who;
            who.CurrentToolIndex = 0;
            // stand next to the tile, facing it, as a player would
            who.Position = new Vector2(tile.X * 64, (tile.Y + 1) * 64);
            who.FacingDirection = 0;
            if (tool is MeleeWeapon mw)
            {
                Game1.player.CurrentToolIndex = 0;
                if (Game1.player.Items.Count > 0) Game1.player.Items[0] = mw;
                mw.lastUser = who;
                mw.DoDamage(farm, (int)tile.X * 64 + 32, (int)tile.Y * 64 + 32, 0, 1, who);
                return;
            }
            tool.DoFunction(farm, (int)tile.X * 64 + 32, (int)tile.Y * 64 + 32, 1, who);
        }

        /// <summary>Centers the camera on the scene, keeps the farmer out of view, and saves the next rendered frame
        /// (the game's own drawing, HUD included) as a PNG.</summary>
        private IEnumerator Shot(Farm farm, string name, JObject result, string key)
        {
            int ox = sceneOrigin.X, oy = sceneOrigin.Y;
            Game1.player.Position = new Vector2((ox + 2) * 64, (oy - 9) * 64);   // above the frame, out of view
            Game1.viewportFreeze = true;
            Game1.viewport.X = (ox * 64 + 64) - Game1.viewport.Width / 2;   // scene columns -2..3
            Game1.viewport.Y = oy * 64 - 290;                                   // rows 0..1 low in the frame, room for tree crowns
            if (Game1.eventUp && Game1.CurrentEvent != null) { Log("ending a cutscene before the shot"); Game1.CurrentEvent.skipEvent(); }
            yield return (Func<bool>)(() => !Game1.eventUp && Game1.activeClickableMenu == null);
            yield return 10;
            capturePath = Path.Combine(outDir, name + ".png");
            captured = false;
            yield return (Func<bool>)(() => captured);
            result[key] = capturePath;
            result[key + "_viewport"] = new JArray(Game1.viewport.X, Game1.viewport.Y, Game1.viewport.Width, Game1.viewport.Height);
            Game1.viewportFreeze = false;
            yield return 2;
        }

        private int waitedTicks;
        private Point sceneOrigin;
        private string capturePath;
        private bool captured = true;

        private void OnRendered(object sender, RenderedEventArgs e)
        {
            if (captured || capturePath == null) return;
            var gd = Game1.graphics.GraphicsDevice;
            var screen = Helper.Reflection.GetField<Microsoft.Xna.Framework.Graphics.RenderTarget2D>(Game1.game1, "_screen").GetValue();
            if (screen != null)
            {
                using (var fs = File.Create(capturePath))
                    screen.SaveAsPng(fs, screen.Width, screen.Height);   // the world at native pixel scale, without HUD
            }
            else
            {
                int w = gd.PresentationParameters.BackBufferWidth, h = gd.PresentationParameters.BackBufferHeight;
                var data = new Color[w * h];
                gd.GetBackBufferData(data);
                using (var tex = new Microsoft.Xna.Framework.Graphics.Texture2D(gd, w, h))
                using (var fs = File.Create(capturePath))
                {
                    tex.SetData(data);
                    tex.SaveAsPng(fs, w, h);
                }
            }
            captured = true;
        }

        private JObject Dump(Farm farm, int ox, int oy, JObject sc)
        {
            var o = new JObject();
            var tiles = new HashSet<(int, int)>();
            foreach (JObject t in sc["tiles"]) tiles.Add(((int)t["d"][0], (int)t["d"][1]));
            foreach (JArray d in sc["watch"] ?? new JArray()) tiles.Add(((int)d[0], (int)d[1]));
            foreach (var (dx, dy) in tiles)
            {
                Vector2 tile = new Vector2(ox + dx, oy + dy);
                var s = new JObject();
                if (farm.terrainFeatures.TryGetValue(tile, out var tf))
                {
                    s["tf"] = tf.GetType().Name;
                    if (tf is HoeDirt hd)
                    {
                        s["watered"] = hd.state.Value == HoeDirt.watered;
                        if (hd.crop != null)
                            s["crop"] = new JObject
                            {
                                ["seed"] = hd.crop.netSeedIndex.Value, ["harvest"] = hd.crop.indexOfHarvest.Value,
                                ["phase"] = hd.crop.currentPhase.Value, ["phases"] = hd.crop.phaseDays.Count,
                                ["day_of_phase"] = hd.crop.dayOfCurrentPhase.Value, ["grown"] = hd.crop.fullyGrown.Value,
                                ["dead"] = hd.crop.dead.Value, ["ready"] = hd.readyForHarvest()
                            };
                    }
                    if (tf is Tree tr) s["tree"] = new JObject { ["stage"] = tr.growthStage.Value, ["stump"] = tr.stump.Value, ["health"] = tr.health.Value, ["falling"] = tr.falling.Value };
                    if (tf is FruitTree ft) s["fruittree"] = new JObject { ["stage"] = ft.growthStage.Value, ["fruit"] = ft.fruit.Count, ["days_until_mature"] = ft.daysUntilMature.Value, ["stump"] = ft.stump.Value };
                }
                if (farm.objects.TryGetValue(tile, out var ob))
                {
                    var j = new JObject { ["id"] = ob.QualifiedItemId, ["name"] = ob.Name, ["on"] = ob.IsOn, ["held"] = ob.heldObject.Value?.QualifiedItemId, ["ready_in"] = ob.MinutesUntilReady };
                    if (ob is Chest ch) j["items"] = new JArray(ch.Items.Where(x => x != null).Select(x => $"{x.QualifiedItemId}x{x.Stack}"));
                    if (ob is Fence fe) j["health"] = fe.health.Value;
                    s["obj"] = j;
                }
                var fu = farm.furniture.FirstOrDefault(f => f.TileLocation == tile);
                if (fu != null) s["furniture"] = new JObject { ["id"] = fu.QualifiedItemId, ["held"] = fu.heldObject.Value?.QualifiedItemId };
                s["diggable"] = farm.doesTileHaveProperty((int)tile.X, (int)tile.Y, "Diggable", "Back") != null;
                o[$"{dx},{dy}"] = s;
            }
            var r = new Rectangle((ox - 6) * 64, (oy - 6) * 64, 13 * 64, 13 * 64);
            o["debris"] = new JArray(farm.debris.Where(d => d.item != null || d.itemId.Value != null)
                .Where(d => d.Chunks.Any(c => r.Contains((int)c.position.X, (int)c.position.Y)))
                .Select(d => $"{d.item?.QualifiedItemId ?? d.itemId.Value}x{d.Chunks.Count}"));
            return o;
        }
    }
}
