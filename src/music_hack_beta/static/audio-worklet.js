class MRT2StreamProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.left = [];
    this.right = [];
    this.readIndex = 0;
    this.queuedSamples = 0;
    this.underruns = 0;
    this.gain = 1;
    this.targetGain = 1;
    this.midiGateEnabled = false;
    this.midiGateTarget = 1;
    this.midiGateValue = 1;
    this.loopTracks = [];
    this.loopPlaying = false;
    this.loopSampleIndex = 0;
    this.loopLengthSamples = 0;
    this.recording = false;
    this.recordLength = 0;
    this.maxRecordSamples = sampleRate * 180;
    this.recordLeft = new Float32Array(this.maxRecordSamples);
    this.recordRight = new Float32Array(this.maxRecordSamples);
    this.metricSamples = 0;
    this.mixLeft = 0;
    this.mixRight = 0;

    this.port.onmessage = (event) => {
      const msg = event.data;
      if (msg.type === 'audio') {
        const interleaved = new Float32Array(msg.buffer);
        const frames = interleaved.length / 2;
        const l = new Float32Array(frames);
        const r = new Float32Array(frames);
        for (let i = 0; i < frames; i++) {
          l[i] = interleaved[i * 2];
          r[i] = interleaved[i * 2 + 1];
        }
        this.left.push(l);
        this.right.push(r);
        this.queuedSamples += frames;
      } else if (msg.type === 'clear') {
        this.left = [];
        this.right = [];
        this.readIndex = 0;
        this.queuedSamples = 0;
      } else if (msg.type === 'gain') {
        this.targetGain = msg.value;
      } else if (msg.type === 'midiGate') {
        this.midiGateEnabled = msg.enabled;
        this.midiGateTarget = msg.active ? 1 : 0;
      } else if (msg.type === 'addLoopTrack') {
        this.addLoopTrack(msg.track);
      } else if (msg.type === 'updateLoopTrack') {
        this.updateLoopTrack(msg.track);
      } else if (msg.type === 'clearLoopTracks') {
        this.loopTracks = [];
        this.loopPlaying = false;
        this.loopSampleIndex = 0;
        this.loopLengthSamples = 0;
        this.resetRecording();
      } else if (msg.type === 'playLoops') {
        this.loopPlaying = true;
        this.loopSampleIndex = Math.max(0, msg.startSample || 0);
      } else if (msg.type === 'stopLoops') {
        this.loopPlaying = false;
      } else if (msg.type === 'startLoopRecording') {
        this.startLoopRecording();
      } else if (msg.type === 'stopLoopRecording') {
        this.stopLoopRecording(msg);
      }
    };
  }

  startLoopRecording() {
    this.resetRecording();
    this.recording = true;
  }

  resetRecording() {
    this.recording = false;
    this.recordLength = 0;
  }

  writeRecordingSample(left, right) {
    if (this.recordLength >= this.maxRecordSamples) return;
    this.recordLeft[this.recordLength] = left;
    this.recordRight[this.recordLength] = right;
    this.recordLength += 1;
  }

  stopLoopRecording(msg) {
    this.recording = false;
    const left = new Float32Array(this.recordLength);
    const right = new Float32Array(this.recordLength);
    left.set(this.recordLeft.subarray(0, this.recordLength));
    right.set(this.recordRight.subarray(0, this.recordLength));
    this.recordLength = 0;
    this.port.postMessage({
      type: 'loopRecorded',
      padIndex: msg.padIndex,
      offsetPct: msg.offsetPct,
      left: left.buffer,
      right: right.buffer,
    }, [left.buffer, right.buffer]);
  }

  addLoopTrack(track) {
    const next = {
      id: track.id,
      left: new Float32Array(track.left),
      right: new Float32Array(track.right),
      offsetSamples: Math.max(0, track.offsetSamples | 0),
      playSamples: Math.max(1, track.playSamples | 0),
      sourceStartSamples: Math.max(0, track.sourceStartSamples | 0),
      sourceEndSamples: Math.max(1, track.sourceEndSamples | 0),
      gain: Number(track.gain),
      effect: track.effect || 'none',
      effectAmount: Number(track.effectAmount || 0),
      lpL: 0,
      lpR: 0,
      hpPrevL: 0,
      hpPrevR: 0,
      hpL: 0,
      hpR: 0,
      tremoloPhase: 0,
    };
    this.loopLengthSamples = Math.max(this.loopLengthSamples, track.loopLengthSamples | 0);
    this.loopTracks = this.loopTracks.filter(item => item.id !== next.id).concat(next);
  }

  updateLoopTrack(track) {
    const existing = this.loopTracks.find(item => item.id === track.id);
    if (!existing) return;
    existing.offsetSamples = Math.max(0, track.offsetSamples | 0);
    existing.playSamples = Math.max(1, track.playSamples | 0);
    existing.sourceStartSamples = Math.max(0, track.sourceStartSamples | 0);
    existing.sourceEndSamples = Math.max(existing.sourceStartSamples + 1, track.sourceEndSamples | 0);
    existing.gain = Number(track.gain);
    existing.effect = track.effect || 'none';
    existing.effectAmount = Number(track.effectAmount || 0);
  }

  loopSample(track, loopPos) {
    this.mixLeft = 0;
    this.mixRight = 0;
    if (!this.loopLengthSamples) return;
    const rel = (loopPos - track.offsetSamples + this.loopLengthSamples) % this.loopLengthSamples;
    if (rel >= track.playSamples) return;
    const sourceLength = Math.max(1, Math.min(track.left.length, track.sourceEndSamples) - track.sourceStartSamples);
    const sourceIndex = track.sourceStartSamples + (rel % sourceLength);
    this.applyTrackEffect(track, track.left[sourceIndex] * track.gain, track.right[sourceIndex] * track.gain);
  }

  applyTrackEffect(track, left, right) {
    const amount = Math.max(0, Math.min(1, track.effectAmount || 0));
    if (amount <= 0 || track.effect === 'none') {
      this.mixLeft = left;
      this.mixRight = right;
      return;
    }

    if (track.effect === 'lowpass') {
      const alpha = 0.04 + (1 - amount) * 0.42;
      track.lpL += (left - track.lpL) * alpha;
      track.lpR += (right - track.lpR) * alpha;
      this.mixLeft = track.lpL;
      this.mixRight = track.lpR;
      return;
    }

    if (track.effect === 'highpass') {
      const alpha = 0.985 - amount * 0.22;
      const hpL = alpha * (track.hpL + left - track.hpPrevL);
      const hpR = alpha * (track.hpR + right - track.hpPrevR);
      track.hpPrevL = left;
      track.hpPrevR = right;
      track.hpL = hpL;
      track.hpR = hpR;
      this.mixLeft = hpL;
      this.mixRight = hpR;
      return;
    }

    if (track.effect === 'distortion') {
      const drive = 1 + amount * 24;
      this.mixLeft = Math.tanh(left * drive) / Math.tanh(drive);
      this.mixRight = Math.tanh(right * drive) / Math.tanh(drive);
      return;
    }

    if (track.effect === 'tremolo') {
      const rate = 2 + amount * 10;
      track.tremoloPhase = (track.tremoloPhase + rate / sampleRate) % 1;
      const mod = 1 - amount * .85 * (.5 + .5 * Math.sin(track.tremoloPhase * Math.PI * 2));
      this.mixLeft = left * mod;
      this.mixRight = right * mod;
      return;
    }

    this.mixLeft = left;
    this.mixRight = right;
  }

  process(inputs, outputs) {
    const out = outputs[0];
    const lout = out[0];
    const rout = out[1] || out[0];

    for (let i = 0; i < lout.length; i++) {
      this.gain += (this.targetGain - this.gain) * 0.002;
      this.midiGateValue += (this.midiGateTarget - this.midiGateValue) * (this.midiGateTarget > this.midiGateValue ? 0.01 : 0.0007);
      const gateGain = this.midiGateEnabled ? this.midiGateValue : 1;
      let left = 0;
      let right = 0;
      let liveLeft = 0;
      let liveRight = 0;

      if (this.left.length === 0) {
        this.underruns += 1;
      } else {
        const lbuf = this.left[0];
        const rbuf = this.right[0];
        liveLeft = lbuf[this.readIndex] * this.gain * gateGain;
        liveRight = rbuf[this.readIndex] * this.gain * gateGain;
        left += liveLeft;
        right += liveRight;
        this.readIndex += 1;
        this.queuedSamples -= 1;

        if (this.readIndex >= lbuf.length) {
          this.left.shift();
          this.right.shift();
          this.readIndex = 0;
        }
      }

      if (this.recording) {
        this.writeRecordingSample(liveLeft, liveRight);
      }

      if (this.loopPlaying && this.loopLengthSamples > 0) {
        const loopPos = this.loopSampleIndex % this.loopLengthSamples;
        for (const track of this.loopTracks) {
          this.loopSample(track, loopPos);
          left += this.mixLeft;
          right += this.mixRight;
        }
        this.loopSampleIndex += 1;
      }

      lout[i] = Math.max(-1, Math.min(1, left));
      rout[i] = Math.max(-1, Math.min(1, right));
    }

    this.metricSamples += lout.length;
    if (this.metricSamples >= sampleRate / 20) {
      this.metricSamples = 0;
      this.port.postMessage({
        type: 'metrics',
        queuedSamples: this.queuedSamples,
        underruns: this.underruns,
        sampleRate,
        loopPlaying: this.loopPlaying,
        loopPositionSamples: this.loopSampleIndex,
        loopLengthSamples: this.loopLengthSamples,
      });
    }
    return true;
  }
}

registerProcessor('mrt2-stream-processor', MRT2StreamProcessor);
