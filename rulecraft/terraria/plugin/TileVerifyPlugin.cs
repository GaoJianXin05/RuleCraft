using System;
using System.IO;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using Terraria;
using TerrariaApi.Server;
using TShockAPI;

namespace TileVerify
{
    [ApiVersion(2, 1)]
    public class TileVerifyPlugin : TerrariaPlugin
    {
        public override string Name => "TileVerify";
        public override string Author => "RuleCraft";
        public override string Description => "Place tiles, advance time/weather, read tile state for rule verification.";
        public override Version Version => new Version(1, 0, 0);

        private HttpListener? _listener;
        private Thread? _listenerThread;
        private const int HttpPort = 7779;

        // pending deferred read: set by HTTP thread, consumed by game-update hook
        private volatile PendingScene? _pending;

        public TileVerifyPlugin(Main game) : base(game) { }

        public override void Initialize()
        {
            Commands.ChatCommands.Add(new Command("tileverify", CmdVerify, "tv"));
            ServerApi.Hooks.GameUpdate.Register(this, OnGameUpdate);
            StartHttp();
            TShock.Log.ConsoleInfo($"[TileVerify] loaded. HTTP on http://localhost:{HttpPort}/tv/run");
        }

        // ---- HTTP server ----

        private void StartHttp()
        {
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://localhost:{HttpPort}/");
            _listener.Start();
            _listenerThread = new Thread(() =>
            {
                while (_listener.IsListening)
                {
                    try { var ctx = _listener.GetContext(); ThreadPool.QueueUserWorkItem(_ => HandleHttp(ctx)); }
                    catch { break; }
                }
            }) { IsBackground = true, Name = "TileVerify-HTTP" };
            _listenerThread.Start();
        }

        private void HandleHttp(HttpListenerContext ctx)
        {
            string path = ctx.Request.Url?.AbsolutePath ?? "";
            string resp;
            try
            {
                if (path == "/tv/status")
                {
                    resp = $"{{\"ok\":true,\"world\":\"{Main.worldName ?? "?"}\"}}";
                }
                else if (path == "/tv/run" && ctx.Request.HttpMethod == "POST")
                {
                    using var sr = new StreamReader(ctx.Request.InputStream, Encoding.UTF8);
                    string body = sr.ReadToEnd();
                    var ps = new PendingScene(body);
                    // block until game-update thread completes it (timeout 30 s)
                    _pending = ps;
                    if (!ps.Done.Wait(30_000))
                        resp = "{\"ok\":false,\"error\":\"timeout waiting for game update\"}";
                    else
                        resp = ps.Result ?? "{\"ok\":false,\"error\":\"no result\"}";
                }
                else
                {
                    ctx.Response.StatusCode = 404;
                    resp = "{\"ok\":false,\"error\":\"unknown path\"}";
                }
            }
            catch (Exception ex) { resp = $"{{\"ok\":false,\"error\":{JsonSerializer.Serialize(ex.Message)}}}"; }

            try
            {
                byte[] buf = Encoding.UTF8.GetBytes(resp);
                ctx.Response.ContentType = "application/json";
                ctx.Response.ContentLength64 = buf.Length;
                ctx.Response.OutputStream.Write(buf, 0, buf.Length);
                ctx.Response.Close();
            }
            catch { }
        }

        // ---- game-update hook (runs on main game thread) ----

        private void OnGameUpdate(EventArgs _)
        {
            var ps = _pending;
            if (ps == null) return;
            _pending = null;

            try
            {
                var scene = JsonNode.Parse(ps.Body)!.AsObject();

                // 1. set time / weather
                if (scene["daytime"] is JsonNode dn) Main.dayTime = dn.GetValue<bool>();
                if (scene["time"]    is JsonNode tn) Main.time    = tn.GetValue<double>();
                if (scene["rain"]    is JsonNode rn)
                {
                    bool rain = rn.GetValue<bool>();
                    Main.raining = rain;
                    Main.maxRaining = rain ? 1f : 0f;
                }

                // 2. place / remove tiles, trigger TileFrame for each
                if (scene["tiles"] is JsonArray tiles)
                {
                    foreach (var t in tiles)
                    {
                        int x  = t!["x"]!.GetValue<int>();
                        int y  = t["y"]!.GetValue<int>();
                        int tp = t["type"]!.GetValue<int>();
                        if (tp < 0)
                        {
                            WorldGen.KillTile(x, y, noItem: true);
                        }
                        else
                        {
                            WorldGen.PlaceTile(x, y, tp, mute: true, forced: true, plr: -1);
                            var tile = Framing.GetTileSafely(x, y);
                            tile.active(true);
                            tile.type = (ushort)tp;
                        }
                        // reframe this tile and its neighbours so gravity/connectivity triggers
                        WorldGen.TileFrame(x, y, true);
                        WorldGen.TileFrame(x, y - 1, true);
                        WorldGen.TileFrame(x, y + 1, true);
                        NetMessage.SendTileSquare(-1, x, y, 3);
                    }
                }

                // 3. settle liquids
                for (int i = 0; i < 60; i++) Liquid.UpdateLiquid();

                // 4. advance world time (ticks field = number of in-game update steps)
                int ticks = scene["ticks"]?.GetValue<int>() ?? 0;
                for (int i = 0; i < ticks; i++)
                {
                    Main.time += 1.0;
                    if (Main.dayTime  && Main.time >= Main.dayLength)   { Main.time = 0; Main.dayTime = false; }
                    if (!Main.dayTime && Main.time >= Main.nightLength) { Main.time = 0; Main.dayTime = true;  }
                    Liquid.UpdateLiquid();
                }

                // 5. read and check
                var result = new JsonObject
                {
                    ["ok"]      = true,
                    ["daytime"] = Main.dayTime,
                    ["time"]    = Main.time,
                    ["raining"] = Main.raining,
                };

                if (scene["check"] is JsonArray checks)
                {
                    var arr = new JsonArray();
                    foreach (var c in checks)
                    {
                        int x = c!["x"]!.GetValue<int>();
                        int y = c["y"]!.GetValue<int>();
                        var tile = Framing.GetTileSafely(x, y);
                        var cr = new JsonObject
                        {
                            ["x"]      = x,
                            ["y"]      = y,
                            ["active"] = tile.active(),
                            ["type"]   = (int)tile.type,
                            ["liquid"] = (int)tile.liquid,
                            ["lava"]   = tile.lava(),
                        };
                        if (c["expect_active"] is JsonNode ea) cr["match_active"] = tile.active() == ea.GetValue<bool>();
                        if (c["expect_type"]   is JsonNode et) cr["match_type"]   = tile.type     == et.GetValue<int>();
                        arr.Add(cr);
                    }
                    result["checks"] = arr;
                }

                ps.Result = result.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
            }
            catch (Exception ex)
            {
                ps.Result = $"{{\"ok\":false,\"error\":{JsonSerializer.Serialize(ex.Message)}}}";
                TShock.Log.ConsoleError($"[TileVerify] scene error: {ex}");
            }
            finally { ps.Done.Set(); }
        }

        // ---- /tv chat command (convenience, same logic) ----

        private void CmdVerify(CommandArgs args)
        {
            if (args.Parameters.Count < 1) { args.Player.SendErrorMessage("Usage: /tv <scene.json>"); return; }
            string p = string.Join(" ", args.Parameters);
            if (!File.Exists(p)) { args.Player.SendErrorMessage($"[TV] not found: {p}"); return; }
            string body = File.ReadAllText(p);
            var ps = new PendingScene(body);
            _pending = ps;
            if (ps.Done.Wait(30_000) && ps.Result != null)
                args.Player.SendSuccessMessage($"[TV] {ps.Result}");
            else
                args.Player.SendErrorMessage("[TV] timeout");
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                Commands.ChatCommands.RemoveAll(c => c.Name == "tv");
                ServerApi.Hooks.GameUpdate.Deregister(this, OnGameUpdate);
                try { _listener?.Stop(); } catch { }
            }
            base.Dispose(disposing);
        }

        private sealed class PendingScene
        {
            public string Body;
            public string? Result;
            public ManualResetEventSlim Done = new ManualResetEventSlim(false);
            public PendingScene(string body) { Body = body; }
        }
    }
}
