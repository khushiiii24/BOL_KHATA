// Records the microphone as a 16 kHz mono WAV file.
// Why: browsers record WebM by default, but Gnani Prisma accepts WAV/MP3/OGG/FLAC/AAC/M4A.
// It stops by itself when you have been quiet for 2.5 seconds, so a short pause in the middle
// of "...2000 का सामान लिया [pause] और 1000 जमा किए" does not cut the sentence.

const TARGET_RATE = 16000;

export class WavRecorder {
  async start({ onLevel, onSilence, onNoSpeech, maxMs = 28000, silenceMs = 2500, minMs = 3000, noSpeechMs = 0 } = {}) {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.ctx = new Ctx();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.proc = this.ctx.createScriptProcessor(4096, 1, 1);
    this.chunks = [];
    this.startedAt = performance.now();

    let noise = null, heard = false, lastLoud = performance.now(), fired = false;
    const fire = () => { if (!fired) { fired = true; onSilence && onSilence(); } };

    this.proc.onaudioprocess = (e) => {
      const data = e.inputBuffer.getChannelData(0);
      this.chunks.push(new Float32Array(data));
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
      const rms = Math.sqrt(sum / data.length);
      onLevel && onLevel(Math.min(1, rms * 8));

      // Background noise level: falls quickly to the quietest moments, rises very slowly.
      // (If you start talking the moment you tap, your voice is not mistaken for "noise".)
      if (noise === null) noise = rms;
      else if (rms < noise) noise = (noise + rms) / 2;
      else noise += (rms - noise) * 0.002;
      const threshold = Math.min(0.045, Math.max(0.012, noise * 3));

      const now = performance.now();
      if (rms > threshold) { heard = true; lastLoud = now; }
      const longEnough = now - this.startedAt > minMs;
      if (heard && longEnough && now - lastLoud > silenceMs) fire(); // quiet for 2.5 s after speaking
      // talk-back mode: nobody spoke at all -> end the conversation quietly
      if (!heard && noSpeechMs && now - this.startedAt > noSpeechMs && !fired) { fired = true; onNoSpeech && onNoSpeech(); }
      if (now - this.startedAt > maxMs) fire();                      // Gnani REST accepts up to 30 s
    };
    this.source.connect(this.proc);
    this.proc.connect(this.ctx.destination);
  }

  async stop() {
    if (!this.ctx) return null;
    this.proc.disconnect();
    this.source.disconnect();
    this.stream.getTracks().forEach((t) => t.stop());
    const rate = this.ctx.sampleRate;
    await this.ctx.close();
    this.ctx = null;

    const length = this.chunks.reduce((n, c) => n + c.length, 0);
    const all = new Float32Array(length);
    let offset = 0;
    for (const c of this.chunks) { all.set(c, offset); offset += c.length; }
    const samples = downsample(all, rate, TARGET_RATE);
    return { blob: encodeWav(samples, TARGET_RATE), seconds: samples.length / TARGET_RATE };
  }
}

function downsample(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio), end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

function encodeWav(samples, rate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buffer);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
