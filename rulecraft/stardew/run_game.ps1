# Starts Stardew Valley with SMAPI (the SceneLab mod runs jobs/job.json) and moves its windows off-screen, so the game
# keeps drawing (screenshots need frames) without covering the desktop. Usage: powershell -File run_game.ps1
$game = "C:\Program Files (x86)\Steam\steamapps\common\Stardew Valley"
Add-Type -Namespace SL -Name U -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetWindowPos(System.IntPtr h, System.IntPtr after, int x, int y, int cx, int cy, uint flags);
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, System.IntPtr l);
public delegate bool EnumProc(System.IntPtr h, System.IntPtr l);
[DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(System.IntPtr h, out int pid);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr h);
'@
$p = Start-Process -FilePath "$game\StardewModdingAPI.exe" -WorkingDirectory $game -WindowStyle Minimized -PassThru
$moved = @{}
for ($k = 0; $k -lt 40; $k++) {
    Start-Sleep -Milliseconds 1500
    $cb = [SL.U+EnumProc]{
        param($h, $l)
        $id = 0
        [void][SL.U]::GetWindowThreadProcessId($h, [ref]$id)
        if ($id -eq $p.Id -and [SL.U]::IsWindowVisible($h)) {
            [void][SL.U]::SetWindowPos($h, [IntPtr]::Zero, -4000, -4000, 0, 0, 0x0001 -bor 0x0004 -bor 0x0010)
            $script:moved[$h] = 1
        }
        return $true
    }
    [void][SL.U]::EnumWindows($cb, [IntPtr]::Zero)
}
"pid $($p.Id); windows moved off-screen: $($moved.Count)"
