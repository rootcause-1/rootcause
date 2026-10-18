# Your own voice on the demo video

How the final cut (`video/out/rootcause-demo-final.mp4`, 4:39) got Yash's voice:

1. `asr.py`: word-level transcription of the recordings (faster-whisper small.en).
2. `align.py`: every sentence of `../script2.py` matched to the recorded words (start/end per sentence).
3. `build_voice.py OUT`: one file per segment, edges trimmed by loudness, pauses over 0.38 s shortened to 0.26 s
   (silence only, never words), sentence start times for the edit.
4. `level.py OUT`: every segment brought to the same speech level (the recordings differed by ~6 dB).
5. Copy OUT to `../voice2`, then `python ../mgbuild.py` and `python ../render2.py`: animations and live shots re-time
   to the voice; finally loudness-normalise to -16 LUFS.
