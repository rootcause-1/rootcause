# Text-to-speech with the built-in Windows OneCore voices (no network): one WAV per line of a script.
# Usage: powershell -File video/tts.ps1 -Script video/build/narration.json -Out video/build/audio -Voice "Microsoft Mark"
# narration.json = [{"id": "s01", "text": "..."}, ...]
param(
  [Parameter(Mandatory = $true)][string]$Script,
  [Parameter(Mandatory = $true)][string]$Out,
  [string]$Voice = "Microsoft Mark",
  [double]$Rate = 1.0
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]

$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1" })[0]
function Await($op, [Type]$type) {
  $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
  $task.Wait() | Out-Null
  return $task.Result
}

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$pick = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -like "*$Voice*" } | Select-Object -First 1
if (-not $pick) { throw "voice '$Voice' not found; installed: $(([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ForEach-Object DisplayName) -join ', ')" }
$synth.Voice = $pick
$synth.Options.SpeakingRate = $Rate
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$lines = Get-Content -Raw -Encoding UTF8 $Script | ConvertFrom-Json
foreach ($l in $lines) {
  $stream = Await ($synth.SynthesizeTextToStreamAsync($l.text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
  $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
  $size = [uint32]$stream.Size
  $null = Await ($reader.LoadAsync($size)) ([uint32])
  $bytes = New-Object byte[] $size
  $reader.ReadBytes($bytes)
  [System.IO.File]::WriteAllBytes((Join-Path $Out "$($l.id).wav"), $bytes)
  Write-Output "$($l.id) $size bytes"
}
