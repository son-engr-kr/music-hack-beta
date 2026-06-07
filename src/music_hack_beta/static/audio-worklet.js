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
      }
    };
  }

  process(inputs, outputs) {
    const out = outputs[0];
    const lout = out[0];
    const rout = out[1] || out[0];

    for (let i = 0; i < lout.length; i++) {
      this.gain += (this.targetGain - this.gain) * 0.002;
      this.midiGateValue += (this.midiGateTarget - this.midiGateValue) * (this.midiGateTarget > this.midiGateValue ? 0.01 : 0.0007);
      const gateGain = this.midiGateEnabled ? this.midiGateValue : 1;
      if (this.left.length === 0) {
        lout[i] = 0;
        rout[i] = 0;
        this.underruns += 1;
        continue;
      }

      const lbuf = this.left[0];
      const rbuf = this.right[0];
      lout[i] = lbuf[this.readIndex] * this.gain * gateGain;
      rout[i] = rbuf[this.readIndex] * this.gain * gateGain;
      this.readIndex += 1;
      this.queuedSamples -= 1;

      if (this.readIndex >= lbuf.length) {
        this.left.shift();
        this.right.shift();
        this.readIndex = 0;
      }
    }

    this.port.postMessage({
      type: 'metrics',
      queuedSamples: this.queuedSamples,
      underruns: this.underruns,
      sampleRate,
    });
    return true;
  }
}

registerProcessor('mrt2-stream-processor', MRT2StreamProcessor);
